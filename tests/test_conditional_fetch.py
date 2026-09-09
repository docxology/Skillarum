"""ETag/If-Modified-Since revalidation against a real local HTTP server."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from skillarum.crawler import ConditionalEntry, WebsiteCrawler
from skillarum.models import (
    CrawlConfig,
    ExtractionConfig,
    SourceProfile,
    TargetSpec,
)
from skillarum.pipeline import run_profile


PAGE = "<html><body><main><h1>Page</h1><p>Conditional body.</p></main></body></html>"


def _make_profile(base_url: str) -> SourceProfile:
    return SourceProfile(
        id="cond",
        name="Conditional Site",
        base_url=base_url,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_response_bytes=100_000,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )


def test_304_reuses_cached_content_and_records_revalidated(httpserver) -> None:
    httpserver.expect_request("/page").respond_with_data(
        PAGE, content_type="text/html", headers={"ETag": '"v1"'}
    )
    base_url = httpserver.url_for("/")
    profile = _make_profile(base_url)
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
    entry = crawler.fetch_cache[f"{base_url}page"]
    assert entry.etag == '"v1"'
    assert bundle.pages[0].revalidated is False

    httpserver.clear_all_handlers()
    conditional_requests: list[dict[str, str]] = []

    def handler(request) -> object:  # type: ignore[no-untyped-def]
        conditional_requests.append(
            {
                "if_none_match": request.headers.get("If-None-Match", ""),
                "if_modified_since": request.headers.get("If-Modified-Since", ""),
            }
        )
        import httpx  # noqa: PLC0415 - local import keeps werkzeug out of src

        return httpx.Response(304)

    from werkzeug.wrappers import Response

    def werkzeug_handler(_request) -> Response:  # type: ignore[no-untyped-def]
        return Response(status=304)

    httpserver.expect_request("/page").respond_with_handler(werkzeug_handler)
    with WebsiteCrawler(profile, fetch_cache=dict(crawler.fetch_cache)) as crawler2:
        bundle2 = crawler2.crawl(target)
    page = bundle2.pages[0]
    assert page.revalidated is True
    assert page.status_code == 200
    assert page.content_sha256 == bundle.pages[0].content_sha256
    assert page.text == bundle.pages[0].text
    revalidated_events = [
        event for event in bundle2.events if event.get("status") == "revalidated"
    ]
    assert len(revalidated_events) == 1
    assert revalidated_events[0]["status_code"] == 304
    assert page.content_sha256


def test_conditional_entry_round_trips_through_dict() -> None:
    entry = ConditionalEntry(
        etag='"abc"',
        last_modified="Wed, 01 Jan 2025 00:00:00 GMT",
        content=b"body",
        content_type="text/html",
    )
    restored = ConditionalEntry.from_dict(entry.to_dict())
    assert restored == entry
    assert (
        ConditionalEntry.from_dict(
            {
                "etag": None,
                "last_modified": None,
                "content_b64": "",
                "content_type": "text/plain",
            }
        ).content
        == b""
    )


def test_pipeline_revalidates_on_second_run_with_refresh(
    httpserver, tmp_path: Path
) -> None:
    from werkzeug.wrappers import Response

    seen_validators: list[str] = []
    mode = {"first": True}

    def handler(request) -> Response:  # type: ignore[no-untyped-def]
        if mode["first"]:
            mode["first"] = False
            return Response(
                PAGE, content_type="text/html", headers={"ETag": '"etag-1"'}
            )
        seen_validators.append(request.headers.get("If-None-Match", ""))
        return Response(status=304)

    httpserver.expect_request("/page").respond_with_handler(handler)
    profile = _make_profile(httpserver.url_for("/"))
    targets = (TargetSpec(id="page", name="Page", urls=("/page",)),)
    profile = SourceProfile(
        id=profile.id,
        name=profile.name,
        base_url=profile.base_url,
        crawl=profile.crawl,
        extraction=profile.extraction,
        targets=targets,
    )
    run_profile(profile, output_dir=tmp_path)
    run_profile(profile, output_dir=tmp_path, refresh=True)
    assert seen_validators == ['"etag-1"']
    run_root = next((tmp_path / "runs").glob("*/"))
    acquired = json.loads(
        sorted((run_root / "01_acquire").glob("*.json"))[0].read_text()
    )
    assert acquired["pages"][0]["revalidated"] is True
    fetch_index = json.loads((tmp_path / ".cache/fetches/index.json").read_text())
    assert fetch_index["cache_version"]
    entry = fetch_index["entries"][f"{httpserver.url_for('/')}page"]
    assert entry["etag"] == '"etag-1"'
    assert base64.b64decode(entry["content_b64"]).decode().startswith("<html>")


def test_revalidated_page_uses_cached_body_bytes(httpserver) -> None:
    """A 304 with changed server content must still serve the cached bytes."""
    httpserver.expect_request("/page").respond_with_data(
        PAGE, content_type="text/html", headers={"ETag": '"old"'}
    )
    profile = _make_profile(httpserver.url_for("/"))
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        crawler.crawl(target)
    from werkzeug.wrappers import Response

    def tampered(_request) -> Response:  # type: ignore[no-untyped-def]
        return Response(status=304)

    httpserver.clear_all_handlers()
    httpserver.expect_request("/page").respond_with_handler(tampered)
    with WebsiteCrawler(profile, fetch_cache=dict(crawler.fetch_cache)) as crawler2:
        bundle = crawler2.crawl(target)
    assert "Conditional body." in bundle.pages[0].text
