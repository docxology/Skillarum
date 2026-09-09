"""Fresh, bounded inventories of public HTML, separate from selected skill bundles."""

import gzip
import json
import re
import tarfile
from xml.parsers import expat

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from xml.etree import ElementTree

from .crawler import WebsiteCrawler
from .models import SourceProfile, TargetSpec
from .urls import is_public_http_url, normalize_url, same_origin
from .utils import (
    sha256_bytes,
    sha256_text,
    write_bytes_atomic,
    write_json_atomic,
)


class SnapshotCrawler(WebsiteCrawler):
    """Keep raw receipts while excluding query actions from a content crawl."""

    def __init__(self, profile, output, progress):
        super().__init__(profile)
        self.snapshot_output = output
        self.progress = progress
        self.saved_count = 0
        self.saved_urls: set[str] = set()

    def _target_allows(self, target, url, start_urls):
        # Wiki edit/history/search actions are not canonical content pages.
        return not urlparse(url).query and super()._target_allows(
            target, url, start_urls
        )

    def _parse_page(self, requested_url, response, depth):
        page = super()._parse_page(requested_url, response, depth)
        raw = self.snapshot_output / "raw" / f"{page.content_sha256}.html"
        raw.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(raw, response.content)
        write_json_atomic(
            self.snapshot_output / "pages" / f"{sha256_text(requested_url)}.json",
            page.to_dict(),
        )
        self.saved_urls.update(
            url
            for url in (page.requested_url, page.final_url, page.canonical_url)
            if url
        )
        self.saved_count += 1
        if self.progress and self.saved_count % 50 == 0:
            self.progress(
                f"{self.profile.id}: {self.saved_count} HTML responses retained"
            )
        return page


def _reject_xml_declarations(content: bytes) -> None:
    """Reject any DOCTYPE declaration regardless of the XML encoding.

    Entity definitions are refused at the parser level. A byte sniff cannot
    see declarations in non-UTF-8 encodings (UTF-16), and expanded internal
    entities are unbounded work controlled by the scraped origin.
    """

    parser = expat.ParserCreate()

    def _reject(*_args: object) -> None:
        raise ValueError("sitemap declarations are not supported")

    parser.StartDoctypeDeclHandler = _reject
    try:
        parser.Parse(content, True)
    except expat.ExpatError as exc:
        raise ValueError(f"sitemap XML is not parseable: {exc}") from exc


def scrape_site(
    profile: SourceProfile,
    output_dir: str | Path,
    *,
    seed_urls: tuple[str, ...],
    sitemap_url: str | None = None,
    max_pages: int = 10000,
    max_requests: int = 20000,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Acquire a new snapshot without loading any response or bundle cache.

    A sitemap sweep covers its declared URLs. Link discovery covers canonical,
    query-free same-origin HTML reachable from its seeds. Neither establishes
    that unlinked, protected, dynamically rendered, or non-HTML content was read.
    """
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"snapshot destination must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    crawl = replace(
        profile.crawl,
        follow_links=sitemap_url is None,
        max_pages=max_pages,
        max_requests=max_requests,
        max_depth=50,
        min_delay_seconds=max(profile.crawl.min_delay_seconds, 0.25),
        user_agent="Skillarum/0.2 (+https://github.com/docxology/Skillarum)",
    )
    profile = replace(profile, crawl=crawl)
    receipt = {
        "ok": False,
        "complete": False,
        "profile_id": profile.id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "evidence_origin": "live"
        if is_public_http_url(profile.base_url)
        else "fixture",
        "scope": "sitemap URLs"
        if sitemap_url
        else "reachable canonical same-origin HTML",
        "cache_policy": "new crawler; no prior response or bundle cache",
        "max_pages": max_pages,
        "max_requests": max_requests,
        "excluded": [
            "query URLs",
            "other origins",
            "non-HTML responses",
            "robots-disallowed pages",
        ],
        "sitemap_url": sitemap_url,
        "seeds": list(seed_urls),
    }
    with SnapshotCrawler(profile, output, progress) as crawler:
        try:
            urls = list(seed_urls)
            if sitemap_url:
                if not same_origin(profile.base_url, sitemap_url):
                    raise ValueError("sitemap must share the configured origin")
                response = crawler._request(sitemap_url)
                _reject_xml_declarations(response.content)
                tree = ElementTree.fromstring(response.content)
                if tree.tag.rsplit("}", 1)[-1] != "urlset":
                    raise ValueError(
                        "expected a URL sitemap, not an index or HTML page"
                    )
                urls.extend(
                    element.text
                    for element in tree.findall("{*}url/{*}loc")
                    if element.text
                )
                (output / "sitemap.xml").write_bytes(response.content)
                receipt["sitemap_sha256"] = sha256_bytes(response.content)
                receipt["discovery_events"] = list(crawler.fetcher.events)
            invalid_urls: list[str] = []
            normalized: set[str] = set()
            for url in urls:
                try:
                    if not same_origin(profile.base_url, url) or urlparse(url).query:
                        continue
                    normalized.add(normalize_url(url))
                except (TypeError, ValueError):
                    # One malformed discovery URL must not abort the sweep;
                    # it is recorded and fails completeness explicitly.
                    invalid_urls.append(url)
            urls = sorted(normalized)
            if not urls:
                raise ValueError(
                    "site snapshot requires at least one same-origin content seed"
                )
            target = TargetSpec(
                id="website-snapshot",
                name="Website-Snapshot",
                urls=tuple(urls),
                include_prefixes=("/",),
            )
            bundle = crawler.crawl(target)
            write_json_atomic(output / "bundle.json", bundle.to_dict())
            accepted = crawler.saved_urls
            discovered = set(urls)
            if crawl.follow_links:
                discovered.update(
                    link
                    for page in bundle.pages
                    for link in page.links
                    if crawler._target_allows(target, link, set(urls))
                )
            unresolved = sorted(discovered - accepted)
            receipt.update(
                ok=True,
                complete=not unresolved and not invalid_urls and not bundle.warnings,
                seed_count=len(urls),
                accepted_pages=len(bundle.pages),
                parsed_html_responses=crawler.saved_count,
                discovered_urls=len(discovered),
                unresolved_urls=unresolved,
                invalid_urls=invalid_urls,
                request_count=bundle.request_count,
                warnings=list(bundle.warnings),
                fetched_from=min(p.fetched_at for p in bundle.pages),
                fetched_through=max(p.fetched_at for p in bundle.pages),
                bundle_sha256=sha256_bytes((output / "bundle.json").read_bytes()),
            )
        except Exception as exc:
            # Preserve the receipt and individually saved responses on every
            # failed acquisition; never turn a partial crawl into success.
            receipt["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            write_json_atomic(output / "snapshot.json", receipt)
    return receipt


def _summary_name(archive_name: str) -> str:
    """Summary filename for an archive.

    Only known archive suffixes are stripped, so multi-dot stems such as
    ``v1.2.tar.gz`` keep their full stem instead of collapsing to ``v1``.
    """
    name = archive_name
    for suffix in (".tar.gz", ".tgz", ".tar", ".gz"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f"{name}.json"


def archive_site_snapshot(snapshot_dir: str | Path, archive_path: str | Path) -> dict:
    """Verify raw receipts and preserve the complete inventory in one archive.

    Raw public responses stay outside the publication allowlist. The adjacent
    summary records the archive hash and any unresolved discovered URLs. A
    successful archive operation does not upgrade an incomplete acquisition.
    """
    root, destination = Path(snapshot_dir), Path(archive_path)
    if destination.exists():
        raise ValueError("snapshot archive destination already exists")
    files = sorted(root.rglob("*"))
    if root.is_symlink() or any(path.is_symlink() for path in files):
        raise ValueError("snapshot archive refuses symlinks")
    receipt_path = root / "snapshot.json"
    if not receipt_path.is_file():
        raise ValueError(f"snapshot receipt is missing: {receipt_path}")
    receipt = json.loads(receipt_path.read_text())
    bundle_path = root / "bundle.json"
    if not bundle_path.is_file():
        raise ValueError(f"snapshot bundle is missing: {bundle_path}")
    bundle_bytes = bundle_path.read_bytes()
    if not receipt.get("ok") or sha256_bytes(bundle_bytes) != receipt.get(
        "bundle_sha256"
    ):
        raise ValueError("snapshot bundle is incomplete or has changed")
    bundle = json.loads(bundle_bytes)
    pages = [
        json.loads(path.read_text()) for path in sorted((root / "pages").glob("*.json"))
    ]
    if not pages or len(bundle["pages"]) != receipt["accepted_pages"]:
        raise ValueError("snapshot page counts do not match the acquisition")
    by_request = {page["requested_url"]: page for page in pages}
    if len(by_request) != len(pages):
        raise ValueError("snapshot has duplicate request receipts")
    for page in bundle["pages"]:
        if by_request.get(page["requested_url"]) != page:
            raise ValueError("snapshot bundle page differs from its response receipt")
    for page in pages:
        if not re.fullmatch(r"[0-9a-f]{64}", page["content_sha256"]):
            raise ValueError("snapshot response digest must be SHA-256")
        raw = root / "raw" / f"{page['content_sha256']}.html"
        if not raw.is_file():
            raise ValueError(f"snapshot raw response is missing: {raw.name}")
        if sha256_bytes(raw.read_bytes()) != page["content_sha256"]:
            raise ValueError("snapshot raw response hash mismatch")
    raw_files = {item.name for item in (root / "raw").glob("*.html")}
    referenced = {f"{page['content_sha256']}.html" for page in pages}
    orphans = sorted(raw_files - referenced)
    if orphans:
        raise ValueError(
            "snapshot raw directory contains unreferenced responses: "
            + ", ".join(orphans[:5])
        )
    # A deduplicated bundle can omit a successfully fetched alias. Count its
    # retained response as resolved without counting it as a distinct page.
    served = {
        url
        for page in pages
        for key in ("requested_url", "final_url", "canonical_url")
        if (url := page.get(key))
    }
    unresolved = sorted(set(receipt["unresolved_urls"]) - served)
    summary = dict(receipt)
    summary.update(
        parsed_html_responses=len(pages),
        unresolved_urls=unresolved,
        complete=not unresolved
        and not receipt.get("invalid_urls", [])
        and not receipt["warnings"],
        archive=destination.name,
        raw_response_files=len(raw_files),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Normalize envelope metadata; response content and receipt timestamps are
    # retained verbatim. No archive is extracted during this operation.
    with destination.open("xb") as raw_archive:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_archive, mtime=0
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for path in files:
                    if not path.is_file():
                        continue
                    info = archive.gettarinfo(
                        str(path), arcname=path.relative_to(root).as_posix()
                    )
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    info.mode = 0o644
                    with path.open("rb") as payload:
                        archive.addfile(info, payload)
    summary["archive_sha256"] = sha256_bytes(destination.read_bytes())
    summary["archive_bytes"] = destination.stat().st_size
    write_json_atomic(destination.with_name(_summary_name(destination.name)), summary)
    return summary


def load_snapshot_archives(output_dir: str | Path) -> tuple[dict, ...]:
    """Read summaries only when the named local archive still matches its hash.

    Completeness is re-derived from the archived receipt and page members, so
    an edited summary cannot inflate an incomplete acquisition into a
    complete one.
    """
    root = Path(output_dir) / "source_archives"
    summaries = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink():
            raise ValueError("snapshot summary must not be a symlink")
        try:
            summary = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"snapshot summary is not valid JSON: {path}") from exc
        if not isinstance(summary, dict):
            raise ValueError(f"snapshot summary must be a JSON object: {path}")
        name = summary.get("archive")
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("snapshot archive must be a local filename")
        archive = root / name
        if not archive.is_file():
            raise ValueError(f"snapshot archive is missing: {archive}")
        if archive.is_symlink() or sha256_bytes(archive.read_bytes()) != summary.get(
            "archive_sha256"
        ):
            raise ValueError("snapshot archive hash mismatch")
        with tarfile.open(archive, "r:gz") as capsule:
            try:
                member = capsule.getmember("snapshot.json")
            except KeyError as exc:
                raise ValueError(
                    f"snapshot archive has no receipt member: {archive}"
                ) from exc
            if not member.isfile() or member.size > 5_000_000:
                raise ValueError("invalid snapshot receipt member")
            with capsule.extractfile(member) as payload:
                receipt = json.load(payload)
            # Re-derive display fields an edited summary could inflate from
            # the archived pages instead of trusting the summary.
            served: set[str] = set()
            page_members = 0
            raw_members = 0
            for entry in capsule.getmembers():
                if not entry.isfile():
                    raise ValueError(
                        f"snapshot archive member is not a regular file: {entry.name}"
                    )
                if entry.name.startswith("pages/") and entry.name.endswith(".json"):
                    page_members += 1
                    with capsule.extractfile(entry) as page_payload:
                        page = json.load(page_payload)
                    for key in ("requested_url", "final_url", "canonical_url"):
                        if page.get(key):
                            served.add(page[key])
                elif entry.name.startswith("raw/") and entry.name.endswith(".html"):
                    raw_members += 1
        for key in (
            "profile_id",
            "accepted_pages",
            "discovered_urls",
            "request_count",
            "seed_count",
            "started_at",
            "finished_at",
            "evidence_origin",
            "scope",
            "warnings",
            "invalid_urls",
            "bundle_sha256",
            "parsed_html_responses",
            "fetched_from",
            "fetched_through",
        ):
            if summary.get(key) != receipt.get(key):
                raise ValueError(
                    f"snapshot summary differs from archived receipt: {key}"
                )
        derived_unresolved = sorted(set(receipt.get("unresolved_urls", [])) - served)
        if summary.get("unresolved_urls") != derived_unresolved:
            raise ValueError(
                "snapshot summary unresolved URLs differ from the archived receipt"
            )
        derived_complete = (
            not derived_unresolved
            and not receipt.get("invalid_urls", [])
            and not receipt.get("warnings")
        )
        if summary.get("complete") != derived_complete:
            raise ValueError(
                "snapshot summary completeness differs from the archived receipt"
            )
        if summary.get("raw_response_files") != raw_members:
            raise ValueError(
                "snapshot summary raw response count differs from the archive"
            )
        summaries.append(summary)
    return tuple(summaries)
