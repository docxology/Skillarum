"""TTL-based robots.txt cache behavior against a real local HTTP server."""

from __future__ import annotations

from typing import Any

import pytest
from werkzeug.wrappers import Response

from skillarum.crawler import RobotsCache, WebsiteCrawler
from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec


def _make_profile(base_url: str, *, ttl: float | None = None) -> SourceProfile:
    crawl_kwargs: dict[str, Any] = {
        "respect_robots": True,
        "allow_private_hosts": True,
        "max_pages": 10,
        "max_response_bytes": 100_000,
    }
    if ttl is not None:
        crawl_kwargs["robots_cache_ttl_seconds"] = ttl
    return SourceProfile(
        id="ttl",
        name="TTL Site",
        base_url=base_url,
        crawl=CrawlConfig(**crawl_kwargs),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )


def _page_response() -> Response:
    return Response(
        "<html><body><main><h1>Page</h1><p>Text.</p></main></body></html>",
        content_type="text/html",
    )


def _robots_response(body: str) -> Response:
    return Response(body, content_type="text/plain")


def test_robots_cached_within_ttl_across_targets(httpserver) -> None:
    hits = {"robots": 0}

    def robots_handler(_request: object) -> Response:
        hits["robots"] += 1
        return _robots_response("User-agent: *\nAllow: /\n")

    httpserver.expect_request("/robots.txt").respond_with_handler(robots_handler)
    httpserver.expect_request("/page").respond_with_handler(
        lambda _request: _page_response()
    )
    profile = _make_profile(httpserver.url_for("/"))
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        crawler.crawl(target)
        crawler.crawl(target)
    assert hits["robots"] == 1


def test_zero_ttl_refetches_changed_robots(httpserver) -> None:
    hits = {"robots": 0}
    content = {"body": "User-agent: *\nDisallow: /\n"}

    def robots_handler(_request: object) -> Response:
        hits["robots"] += 1
        return _robots_response(content["body"])

    httpserver.expect_request("/robots.txt").respond_with_handler(robots_handler)
    httpserver.expect_request("/page").respond_with_handler(
        lambda _request: _page_response()
    )
    profile = _make_profile(httpserver.url_for("/"), ttl=0.0)
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        with pytest.raises(Exception, match="no pages"):
            crawler.crawl(target)
        # The site opens up between fetches; zero TTL must observe the change.
        content["body"] = "User-agent: *\nAllow: /\n"
        bundle = crawler.crawl(target)
    assert hits["robots"] == 2
    assert len(bundle.pages) == 1


def test_robots_cache_reuses_parser_before_expiry(httpserver) -> None:
    hits = {"robots": 0}

    def robots_handler(_request: object) -> Response:
        hits["robots"] += 1
        return _robots_response("User-agent: *\nDisallow: /secret\n")

    httpserver.expect_request("/robots.txt").respond_with_handler(robots_handler)
    httpserver.expect_request("/page").respond_with_handler(
        lambda _request: _page_response()
    )
    base_url = httpserver.url_for("/")
    profile = _make_profile(base_url)
    with WebsiteCrawler(profile) as crawler:
        assert crawler._robots.allowed(  # noqa: SLF001 - direct cache probe
            f"{base_url}page", crawler.fetcher, profile.crawl.user_agent
        )
        assert crawler._robots.allowed(
            f"{base_url}page", crawler.fetcher, profile.crawl.user_agent
        )
        assert hits["robots"] == 1
        assert not crawler._robots.allowed(
            f"{base_url}secret", crawler.fetcher, profile.crawl.user_agent
        )
        assert hits["robots"] == 1
        # Expired entries re-fetch instead of reusing a stale parser.
        crawler._robots.ttl_seconds = 0.0
        assert crawler._robots.allowed(
            f"{base_url}page", crawler.fetcher, profile.crawl.user_agent
        )
        assert hits["robots"] == 2


def test_robots_cache_ttl_defaults_and_validation() -> None:
    assert RobotsCache().ttl_seconds == 3600.0
    assert CrawlConfig().robots_cache_ttl_seconds == 3600.0
    with pytest.raises(ValueError, match="non-negative"):
        CrawlConfig.from_mapping({"robots_cache_ttl_seconds": -1})
