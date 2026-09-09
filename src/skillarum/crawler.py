"""Safe, server-rendered HTML acquisition and page selection."""

from __future__ import annotations

import base64
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .models import BundleRecord, PageRecord, RetryConfig, SourceProfile, TargetSpec
from .urls import (
    is_public_http_url,
    normalize_url,
    path_matches,
    resolve_url,
    same_origin,
)
from .utils import sha256_bytes


@dataclass(frozen=True)
class ConditionalEntry:
    """Cached fetch metadata enabling ETag/If-Modified-Since revalidation."""

    etag: str | None
    last_modified: str | None
    content: bytes
    content_type: str = "text/html"

    def to_dict(self) -> dict[str, object]:
        return {
            "etag": self.etag,
            "last_modified": self.last_modified,
            "content_b64": base64.b64encode(self.content).decode("ascii"),
            "content_type": self.content_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ConditionalEntry":
        return cls(
            etag=data.get("etag") if data.get("etag") else None,
            last_modified=data.get("last_modified")
            if data.get("last_modified")
            else None,
            content=base64.b64decode(data["content_b64"]),
            content_type=data.get("content_type", "text/html"),
        )


class CrawlError(RuntimeError):
    """Raised when a target cannot produce any usable pages."""


class RequestLimitExceeded(CrawlError):
    """Raised when all page, redirect, robots, and retry requests are exhausted."""


class PageAbsent(CrawlError):
    """Raised when a fetch definitively shows a page is gone (HTTP 404/410)."""


class Fetcher(Protocol):
    """Acquisition boundary for future browser/JavaScript fetchers."""

    request_count: int

    def fetch(self, url: str, *, kind: str = "page") -> httpx.Response:
        """Fetch one bounded response without following redirects."""


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return seconds if seconds >= 0 else None
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _retryable_status(status_code: int) -> bool:
    return status_code in {408, 429, 500, 502, 503, 504}


class HTTPFetcher:
    """Streaming, rate-limited, retrying implementation of the v1 fetcher."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        max_response_bytes: int,
        max_requests: int,
        min_delay_seconds: float,
        retry: RetryConfig,
        conditional: dict[str, ConditionalEntry] | None = None,
    ) -> None:
        self.client = client
        self.max_response_bytes = max_response_bytes
        self.max_requests = max_requests
        self.min_delay_seconds = min_delay_seconds
        self.retry = retry
        self.conditional = dict(conditional or {})
        self.request_count = 0
        self._last_request_at = 0.0
        self.events: list[dict[str, object]] = []

    def _record(self, **event: object) -> None:
        self.events.append(
            {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        )

    def _reserve(self, url: str, kind: str, attempt: int) -> int:
        if self.request_count >= self.max_requests:
            self._record(
                kind=kind,
                url=url,
                attempt=attempt,
                status="rejected",
                reason="max_requests exceeded",
                request_attempt=False,
            )
            raise RequestLimitExceeded(f"max_requests limit reached at {url}")
        self.request_count += 1
        return self.request_count

    def _sleep_for_rate_limit(self) -> None:
        remaining = self.min_delay_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _read_response(self, url: str, kind: str, attempt: int) -> httpx.Response:
        request_index = self._reserve(url, kind, attempt)
        self._sleep_for_rate_limit()
        self._last_request_at = time.monotonic()
        conditional_headers: dict[str, str] = {}
        cached: ConditionalEntry | None = None
        if kind != "robots":
            cached = self.conditional.get(url)
            if cached is not None:
                if cached.etag:
                    conditional_headers["If-None-Match"] = cached.etag
                if cached.last_modified:
                    conditional_headers["If-Modified-Since"] = cached.last_modified
        started = time.perf_counter()
        try:
            with self.client.stream(
                "GET", url, follow_redirects=False, headers=conditional_headers
            ) as response:
                if response.status_code == 304 and cached is not None:
                    self._record(
                        kind=kind,
                        url=url,
                        attempt=attempt,
                        status="revalidated",
                        status_code=304,
                        bytes=len(cached.content),
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        request_attempt=True,
                        request_index=request_index,
                    )
                    return self._bounded_cached_response(cached, response)
                declared_size = response.headers.get("content-length")
                if declared_size:
                    try:
                        if int(declared_size) > self.max_response_bytes:
                            raise CrawlError(f"response exceeds byte limit: {url}")
                    except ValueError as exc:
                        raise CrawlError(
                            f"invalid Content-Length header: {url}"
                        ) from exc
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        raise CrawlError(f"response exceeds byte limit: {url}")
                    chunks.append(chunk)
                headers = dict(response.headers)
                # httpx.iter_bytes() has already applied content decoding. Do
                # not leave compression metadata on the normalized payload or
                # consumers will attempt a second decompression.
                headers.pop("content-encoding", None)
                headers["content-length"] = str(total)
                bounded = httpx.Response(
                    response.status_code,
                    headers=headers,
                    content=b"".join(chunks),
                    request=response.request,
                    extensions={"revalidated": False},
                )
                self._record(
                    kind=kind,
                    url=url,
                    attempt=attempt,
                    status="received",
                    status_code=response.status_code,
                    bytes=total,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    request_attempt=True,
                    request_index=request_index,
                )
                return bounded
        except (httpx.HTTPError, CrawlError) as exc:
            self._record(
                kind=kind,
                url=url,
                attempt=attempt,
                status="rejected",
                reason=str(exc)[:500],
                duration_ms=int((time.perf_counter() - started) * 1000),
                request_attempt=True,
                request_index=request_index,
            )
            raise

    def _bounded_cached_response(
        self, cached: ConditionalEntry, response: httpx.Response
    ) -> httpx.Response:
        if len(cached.content) > self.max_response_bytes:
            raise CrawlError(
                f"cached response exceeds byte limit: {response.request.url}"
            )
        headers = {
            "content-type": cached.content_type,
            "content-length": str(len(cached.content)),
            "etag": cached.etag or "",
            "last-modified": cached.last_modified or "",
        }
        return httpx.Response(
            200,
            headers=headers,
            content=cached.content,
            request=response.request,
            extensions={"revalidated": True},
        )

    def fetch(self, url: str, *, kind: str = "page") -> httpx.Response:
        """Fetch with bounded retries for transport and transient HTTP failures."""
        for attempt in range(self.retry.max_attempts):
            try:
                response = self._read_response(url, kind, attempt)
            except RequestLimitExceeded:
                raise
            except httpx.HTTPError as exc:
                if attempt + 1 < self.retry.max_attempts:
                    delay = min(
                        self.retry.base_delay_seconds * (2**attempt),
                        self.retry.max_delay_seconds,
                    )
                    self._record(
                        kind=kind,
                        url=url,
                        attempt=attempt,
                        status="retrying",
                        reason=type(exc).__name__,
                        delay_seconds=delay,
                        request_attempt=False,
                    )
                    time.sleep(delay)
                    continue
                raise
            except CrawlError:
                raise
            if (
                _retryable_status(response.status_code)
                and attempt + 1 < self.retry.max_attempts
            ):
                delay_header = _retry_after(response.headers.get("Retry-After"))
                delay = min(
                    delay_header
                    if delay_header is not None
                    else self.retry.base_delay_seconds * (2**attempt),
                    self.retry.max_delay_seconds,
                )
                self._record(
                    kind=kind,
                    url=url,
                    attempt=attempt,
                    status="retrying",
                    status_code=response.status_code,
                    delay_seconds=delay,
                    request_attempt=False,
                )
                time.sleep(delay)
                continue
            return response
        raise CrawlError(f"fetch exhausted retry policy: {url}")  # pragma: no cover


class RobotsCache:
    """TTL-based per-origin robots.txt cache using the crawler's fetcher.

    A common site configuration 3xx-redirects ``/robots.txt`` (for example
    http->https or to a canonical host).  Such redirects are followed in a
    bounded number of hops, re-validating that every target remains an
    allowed public destination.  Any other non-success response is treated as
    a fail-closed rejection rather than an allow-all fallback.

    Cached parsers expire after ``ttl_seconds`` (default one hour,
    configurable per profile via ``crawl.robots_cache_ttl_seconds``).  A
    non-positive TTL disables caching so every ``allowed`` call re-fetches.
    """

    _redirect_limit = 5

    def __init__(self, *, ttl_seconds: float = 3600.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._fetched_at: dict[str, float] = {}
        self.errors: list[str] = []

    def _expired(self, robots_url: str) -> bool:
        if robots_url not in self._parsers:
            return True
        if self.ttl_seconds <= 0:
            return True
        fetched_at = self._fetched_at.get(robots_url)
        if fetched_at is None:
            return True
        return (time.monotonic() - fetched_at) >= self.ttl_seconds

    def _store(self, robots_url: str, parser: RobotFileParser | None) -> None:
        self._parsers[robots_url] = parser
        if parser is not None:
            self._fetched_at[robots_url] = time.monotonic()
        else:
            self._fetched_at.pop(robots_url, None)

    def allowed(
        self,
        url: str,
        fetcher: Fetcher,
        user_agent: str,
        *,
        allow_private: bool = False,
    ) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if not self._expired(robots_url):
            parser = self._parsers[robots_url]
            return parser is not None and parser.can_fetch(user_agent, url)
        self._parsers.pop(robots_url, None)
        self._fetched_at.pop(robots_url, None)
        parser = RobotFileParser(robots_url)
        current_url = robots_url
        redirect_count = 0
        try:
            while True:
                response = fetcher.fetch(current_url, kind="robots")
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        message = (
                            f"robots.txt redirect has no Location header: {current_url}"
                        )
                        self.errors.append(message)
                        self._store(robots_url, None)
                        return False
                    redirect_count += 1
                    if redirect_count > self._redirect_limit:
                        message = f"robots.txt redirect limit exceeded: {robots_url}"
                        self.errors.append(message)
                        self._store(robots_url, None)
                        return False
                    try:
                        current_url = resolve_url(current_url, location)
                    except (TypeError, ValueError):
                        message = (
                            f"robots.txt redirect target is invalid: {current_url}"
                        )
                        self.errors.append(message)
                        self._store(robots_url, None)
                        return False
                    if not is_public_http_url(
                        current_url,
                        allow_private=allow_private,
                        resolve_dns=True,
                    ):
                        message = f"robots.txt redirected to a private or unsafe URL: {current_url}"
                        self.errors.append(message)
                        self._store(robots_url, None)
                        return False
                    continue
                if response.status_code == 404:
                    parser.parse([])
                elif 200 <= response.status_code < 300:
                    parser.parse(response.text.splitlines())
                else:
                    message = f"robots.txt returned HTTP {response.status_code}: {current_url}"
                    self.errors.append(message)
                    self._store(robots_url, None)
                    return False
                self._store(robots_url, parser)
                break
        except RequestLimitExceeded:
            raise
        except (httpx.HTTPError, CrawlError) as exc:
            self.errors.append(f"robots.txt fetch failed for {robots_url}: {exc}")
            self._store(robots_url, None)
            return False
        parser = self._parsers[robots_url]
        return parser is not None and parser.can_fetch(user_agent, url)


class WebsiteCrawler:
    """Fetch and normalize a static website target."""

    def __init__(
        self,
        profile: SourceProfile,
        *,
        refresh: bool = False,
        fetcher: Fetcher | None = None,
        fetch_cache: dict[str, ConditionalEntry] | None = None,
    ) -> None:
        self.profile = profile
        self.refresh = refresh
        self._robots = RobotsCache(ttl_seconds=profile.crawl.robots_cache_ttl_seconds)
        self.events: list[dict[str, object]] = []
        self.fetch_cache: dict[str, ConditionalEntry] = dict(fetch_cache or {})
        self.client = httpx.Client(
            follow_redirects=False,
            headers={"User-Agent": profile.crawl.user_agent},
            timeout=profile.crawl.request_timeout_seconds,
            trust_env=False,
        )
        self.fetcher: Fetcher = fetcher or HTTPFetcher(
            self.client,
            max_response_bytes=profile.crawl.max_response_bytes,
            max_requests=profile.crawl.max_requests,
            min_delay_seconds=profile.crawl.min_delay_seconds,
            retry=profile.crawl.retry,
            conditional=self.fetch_cache,
        )

    @property
    def request_count(self) -> int:
        return self.fetcher.request_count

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "WebsiteCrawler":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _reject(self, url: str, reason: str, *, kind: str = "selection") -> None:
        self.events.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "url": url,
                "status": "rejected",
                "reason": reason,
                "request_attempt": False,
            }
        )

    def _request(self, url: str) -> httpx.Response:
        current_url = normalize_url(url)
        for redirect_count in range(self.profile.crawl.max_redirects + 1):
            if not is_public_http_url(
                current_url,
                allow_private=self.profile.crawl.allow_private_hosts,
                resolve_dns=False,
            ):
                self._reject(current_url, "unsafe or unsupported URL")
                raise CrawlError(f"unsafe or unsupported URL rejected: {current_url}")
            if self.profile.crawl.same_origin_only and not same_origin(
                self.profile.base_url, current_url
            ):
                self._reject(current_url, "cross-origin URL")
                raise CrawlError(f"cross-origin URL rejected: {current_url}")
            if not is_public_http_url(
                current_url,
                allow_private=self.profile.crawl.allow_private_hosts,
                resolve_dns=True,
            ):
                self._reject(current_url, "unsafe or unsupported URL")
                raise CrawlError(f"unsafe or unsupported URL rejected: {current_url}")
            if self.profile.crawl.respect_robots and not self._robots.allowed(
                current_url,
                self.fetcher,
                self.profile.crawl.user_agent,
                allow_private=self.profile.crawl.allow_private_hosts,
            ):
                self._reject(current_url, "robots.txt disallows URL", kind="robots")
                raise CrawlError(f"robots.txt disallows URL: {current_url}")
            response = self.fetcher.fetch(
                current_url, kind="page" if redirect_count == 0 else "redirect"
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    self._reject(
                        current_url,
                        "redirect response has no Location header",
                        kind="redirect",
                    )
                    raise CrawlError(
                        f"redirect response has no Location header: {current_url}"
                    )
                next_url = resolve_url(current_url, location)
                self.events.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "kind": "redirect",
                        "url": current_url,
                        "status": "redirect",
                        "status_code": response.status_code,
                        "location": next_url,
                        "request_attempt": False,
                    }
                )
                if redirect_count == self.profile.crawl.max_redirects:
                    self._reject(next_url, "redirect limit exceeded", kind="redirect")
                    raise CrawlError(f"redirect limit exceeded: {url}")
                current_url = next_url
                continue
            return response
        raise CrawlError(f"redirect limit exceeded: {url}")

    def _main_node(self, soup: BeautifulSoup):
        selector = self.profile.extraction.main_selector
        if selector:
            try:
                selected = soup.select_one(selector)
            except Exception as exc:  # BeautifulSoup selector errors vary by parser.
                raise CrawlError(
                    f"invalid extraction selector {selector!r}: {exc}"
                ) from exc
            if selected is not None:
                return selected
        return (
            soup.select_one("article") or soup.select_one("main") or soup.body or soup
        )

    def _parse_page(
        self, requested_url: str, response: httpx.Response, depth: int
    ) -> PageRecord:
        revalidated = bool(response.extensions.get("revalidated"))
        final_url = normalize_url(str(response.url))
        if not is_public_http_url(
            final_url,
            allow_private=self.profile.crawl.allow_private_hosts,
            resolve_dns=True,
        ):
            raise CrawlError(f"unsafe redirected URL rejected: {final_url}")
        if self.profile.crawl.same_origin_only and not same_origin(
            self.profile.base_url, final_url
        ):
            raise CrawlError(f"redirected outside allowed origin: {final_url}")
        if not 200 <= response.status_code < 300:
            if response.status_code in {404, 410}:
                raise PageAbsent(f"HTTP {response.status_code}: {final_url}")
            raise CrawlError(f"HTTP {response.status_code}: {final_url}")
        content_type = response.headers.get("content-type", "").lower()
        if (
            content_type
            and "html" not in content_type
            and "text/plain" not in content_type
        ):
            raise CrawlError(
                f"non-HTML response rejected ({content_type}): {final_url}"
            )
        soup = BeautifulSoup(response.content, "html.parser")
        title_node = soup.find("title")
        title = title_node.get_text(" ", strip=True) if title_node else ""
        root = self._main_node(soup)
        for selector in self.profile.extraction.remove_selectors:
            try:
                for node in root.select(selector):
                    node.decompose()
            except Exception as exc:
                raise CrawlError(
                    f"invalid removal selector {selector!r}: {exc}"
                ) from exc
        headings = tuple(
            node.get_text(" ", strip=True)
            for node in root.select("h1, h2, h3, h4, h5, h6")
            if node.get_text(" ", strip=True)
        )
        text = root.get_text(" ", strip=True)
        warnings: list[str] = []
        links_set: set[str] = set()
        for node in root.select("a[href]"):
            raw_href = str(node.get("href", "")).strip()
            if not raw_href:
                continue
            try:
                candidate = resolve_url(final_url, raw_href)
            except (TypeError, ValueError) as exc:
                warnings.append(
                    f"invalid link ignored ({raw_href[:120]}): {type(exc).__name__}"
                )
                continue
            try:
                if self._link_is_allowed(final_url, candidate):
                    links_set.add(candidate)
            except (TypeError, ValueError):
                warnings.append(
                    f"invalid link ignored ({raw_href[:120]}): URL validation failed"
                )
        links = sorted(links_set)
        canonical_node = soup.select_one('link[rel~="canonical"][href]')
        canonical_url = None
        if canonical_node is not None:
            try:
                candidate = resolve_url(final_url, str(canonical_node.get("href")))
            except (TypeError, ValueError):
                candidate = None
                warnings.append("invalid canonical link ignored")
            if candidate and same_origin(self.profile.base_url, candidate):
                canonical_url = candidate
        if not title:
            warnings.append("page has no title")
        if not text:
            warnings.append("page has no extracted text")
        # Observe conditional metadata for later revalidation. On a 304 the
        # synthetic response already carries the cached validator headers.
        self.fetch_cache[final_url] = ConditionalEntry(
            etag=response.headers.get("etag") or None,
            last_modified=response.headers.get("last-modified") or None,
            content=response.content,
            content_type=content_type,
        )
        return PageRecord(
            requested_url=requested_url,
            final_url=final_url,
            canonical_url=canonical_url,
            status_code=response.status_code,
            title=title,
            headings=headings,
            text=text,
            links=tuple(links),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            content_sha256=sha256_bytes(response.content),
            depth=depth,
            revalidated=revalidated,
            warnings=tuple(warnings),
        )

    def _link_is_allowed(self, current_url: str, candidate: str) -> bool:
        if not is_public_http_url(
            candidate,
            allow_private=self.profile.crawl.allow_private_hosts,
            resolve_dns=True,
        ):
            return False
        if self.profile.crawl.same_origin_only:
            return same_origin(self.profile.base_url, candidate)
        return True

    def _target_allows(
        self, target: TargetSpec, url: str, start_urls: set[str]
    ) -> bool:
        if self.profile.crawl.same_origin_only and not same_origin(
            self.profile.base_url, url
        ):
            return False
        if target.exclude_patterns and path_matches(url, target.exclude_patterns):
            return False
        if url in start_urls:
            return True
        path = urlparse(url).path or "/"

        def prefix_matches(prefix: str) -> bool:
            normalized = prefix.strip().rstrip("/") or "/"
            return (
                normalized == "/"
                or path == normalized
                or path.startswith(normalized + "/")
            )

        if target.include_prefixes and any(
            prefix_matches(prefix) for prefix in target.include_prefixes
        ):
            return True
        if target.include_prefixes:
            return False
        if target.include_patterns:
            return path_matches(url, target.include_patterns)
        return self.profile.crawl.follow_links

    def crawl(self, target: TargetSpec) -> BundleRecord:
        """Fetch the target's exact URLs and, when configured, discover a bundle."""
        self.events = []
        if isinstance(self.fetcher, HTTPFetcher):
            self.fetcher.events = []
            self.fetcher.request_count = 0
            self.fetcher._last_request_at = 0.0
        self._robots.errors = []
        start_url_list: list[str] = []
        for candidate in target.urls or (self.profile.base_url,):
            try:
                resolved = resolve_url(self.profile.base_url, candidate)
            except (TypeError, ValueError) as exc:
                raise CrawlError(
                    f"target {target.id!r} has an invalid start URL "
                    f"{candidate!r}: {exc}"
                ) from exc
            if resolved not in start_url_list:
                start_url_list.append(resolved)
        start_urls = set(start_url_list)
        queue = deque((url, 0) for url in start_url_list)
        queued = set(start_urls)
        pages: list[PageRecord] = []
        seen_identity: set[str] = set()
        warnings: list[str] = []
        absent_urls: set[str] = set()
        incomplete = False
        max_pages = min(
            target.max_pages or self.profile.crawl.max_pages,
            self.profile.crawl.max_pages,
        )
        limit_reached = False

        while queue and len(pages) < max_pages:
            requested_url, depth = queue.popleft()
            if not self._target_allows(target, requested_url, start_urls):
                self._reject(requested_url, "target filter")
                continue
            try:
                response = self._request(requested_url)
                page = self._parse_page(requested_url, response, depth)
            except RequestLimitExceeded as exc:
                warnings.append(str(exc))
                limit_reached = True
                break
            except PageAbsent as exc:
                warnings.append(str(exc))
                self._reject(requested_url, str(exc), kind="page")
                absent_urls.add(requested_url)
                continue
            except (CrawlError, httpx.HTTPError, ValueError) as exc:
                warnings.append(str(exc))
                self._reject(requested_url, str(exc), kind="page")
                incomplete = True
                continue
            identity = page.canonical_url or page.final_url
            if identity in seen_identity:
                self._reject(
                    requested_url, "duplicate canonical/final URL", kind="duplicate"
                )
                continue
            seen_identity.add(identity)
            pages.append(page)
            if self.profile.crawl.follow_links and depth < self.profile.crawl.max_depth:
                for link in page.links:
                    if link not in queued and self._target_allows(
                        target, link, start_urls
                    ):
                        queued.add(link)
                        queue.append((link, depth + 1))

        if queue and (
            limit_reached or self.request_count >= self.profile.crawl.max_requests
        ):
            warnings.append(
                f"request limit reached after {self.request_count} request(s); "
                f"accepted pages: {len(pages)}"
            )
            incomplete = True
        if queue and len(pages) >= max_pages:
            warnings.append(f"page limit reached after {self.request_count} request(s)")
            incomplete = True
        warnings.extend(self._robots.errors)
        if not pages:
            details = "; ".join(warnings) or "no usable pages"
            raise CrawlError(f"target {target.id!r} produced no pages: {details}")
        events = tuple(
            dict(event)
            for event in (
                (self.fetcher.events if isinstance(self.fetcher, HTTPFetcher) else [])
                + self.events
            )
        )
        return BundleRecord(
            profile_id=self.profile.id,
            profile_name=self.profile.name,
            target_id=target.id,
            skill_name=target.name,
            pages=tuple(pages),
            created_at=datetime.now(timezone.utc).isoformat(),
            warnings=tuple(dict.fromkeys(warnings)),
            events=events,
            request_count=self.request_count,
            area=self.profile.area,
            absent_urls=tuple(sorted(absent_urls)),
            incomplete=incomplete,
        )
