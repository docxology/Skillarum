"""Test content-diff refresh functionality in pipeline."""

from __future__ import annotations

import json
from pathlib import Path


from skillarum.cli import main
from skillarum.models import CrawlConfig, SourceProfile, TargetSpec
from skillarum.pipeline import bundle_refresh_diff, run_profile


def test_bundle_refresh_diff_detects_changes(fixture_server: str) -> None:
    """bundle_refresh_diff reports added/removed/changed pages by URL."""
    from skillarum.models import BundleRecord, PageRecord

    old_bundle = BundleRecord(
        profile_id="test",
        profile_name="Test",
        target_id="test",
        skill_name="Test",
        pages=(
            PageRecord(
                requested_url="/page1",
                final_url="/page1",
                canonical_url=None,
                status_code=200,
                title="Page 1",
                headings=(),
                text="old content",
                links=(),
                fetched_at="2024-01-01T00:00:00Z",
                content_sha256="old123",
            ),
            PageRecord(
                requested_url="/page2",
                final_url="/page2",
                canonical_url=None,
                status_code=200,
                title="Page 2",
                headings=(),
                text="unchanged",
                links=(),
                fetched_at="2024-01-01T00:00:00Z",
                content_sha256="same456",
            ),
        ),
        created_at="2024-01-01T00:00:00Z",
    )

    new_bundle = BundleRecord(
        profile_id="test",
        profile_name="Test",
        target_id="test",
        skill_name="Test",
        pages=(
            PageRecord(
                requested_url="/page1",
                final_url="/page1",
                canonical_url=None,
                status_code=200,
                title="Page 1",
                headings=(),
                text="new content",
                links=(),
                fetched_at="2024-01-01T01:00:00Z",
                content_sha256="new789",
            ),
            PageRecord(
                requested_url="/page2",
                final_url="/page2",
                canonical_url=None,
                status_code=200,
                title="Page 2",
                headings=(),
                text="unchanged",
                links=(),
                fetched_at="2024-01-01T01:00:00Z",
                content_sha256="same456",
            ),
            PageRecord(
                requested_url="/page3",
                final_url="/page3",
                canonical_url=None,
                status_code=200,
                title="Page 3",
                headings=(),
                text="new page",
                links=(),
                fetched_at="2024-01-01T01:00:00Z",
                content_sha256="added999",
            ),
        ),
        created_at="2024-01-01T01:00:00Z",
    )

    diff = bundle_refresh_diff(old_bundle, new_bundle)
    assert diff["had_previous"]
    assert len(diff["added"]) == 1
    assert diff["added"][0]["url"] == "/page3"
    assert diff["added"][0]["content_sha256"] == "added999"
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["url"] == "/page1"
    assert diff["changed"][0]["old_content_sha256"] == "old123"
    assert diff["changed"][0]["new_content_sha256"] == "new789"
    assert diff["unchanged"] == 1


def test_bundle_refresh_diff_handles_no_previous() -> None:
    """bundle_refresh_diff handles first-time crawls gracefully."""
    from skillarum.models import BundleRecord, PageRecord

    bundle = BundleRecord(
        profile_id="test",
        profile_name="Test",
        target_id="test",
        skill_name="Test",
        pages=(
            PageRecord(
                requested_url="/page",
                final_url="/page",
                canonical_url=None,
                status_code=200,
                title="Page",
                headings=(),
                text="content",
                links=(),
                fetched_at="2024-01-01T00:00:00Z",
                content_sha256="abc123",
            ),
        ),
        created_at="2024-01-01T00:00:00Z",
    )

    diff = bundle_refresh_diff(None, bundle)
    assert not diff["had_previous"]


def test_refresh_flag_produces_diff_in_manifest(
    fixture_server: str, tmp_path: Path
) -> None:
    """Running with --refresh should include refresh diffs in the manifest."""
    profile = SourceProfile(
        id="refresh-test",
        name="Refresh Test",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )

    # First run to establish cache
    run_profile(profile, output_dir=tmp_path)

    # Second run with refresh - should detect no changes (same server)
    run_profile(profile, output_dir=tmp_path, refresh=True)

    manifests = list((tmp_path / "runs").glob("*/manifest.json"))
    refresh_manifest = max(manifests, key=lambda p: p.stat().st_mtime)
    data = json.loads(refresh_manifest.read_text())

    assert data.get("refresh") is True
    assert "refresh_diff" in data
    assert isinstance(data["refresh_diff"], dict)
    # Content should be identical for same server
    if data["refresh_diff"]:
        assert all(
            diff.get("had_previous", False) for diff in data["refresh_diff"].values()
        )


def test_cli_refresh_includes_manifest_diff(
    fixture_server: str, tmp_path: Path
) -> None:
    """CLI run with --refresh includes diff summary in manifest."""
    profile_path = tmp_path / "refresh.yaml"
    profile_path.write_text(f"""
id: refresh-cli-test
name: Refresh CLI Test
base_url: {fixture_server}
crawl:
  respect_robots: false
  allow_private_hosts: true
targets:
  - id: page
    name: Page
    urls: ["/page"]
""")

    # Initial run
    assert (
        main(
            [
                "run",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(tmp_path),
                "--backend",
                "deterministic",
            ]
        )
        == 0
    )

    # Refresh run
    assert (
        main(
            [
                "run",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(tmp_path),
                "--backend",
                "deterministic",
                "--refresh",
            ]
        )
        == 0
    )

    manifests = list((tmp_path / "runs").glob("*/manifest.json"))
    refresh_manifest = max(manifests, key=lambda p: p.stat().st_mtime)
    data = json.loads(refresh_manifest.read_text())

    assert data["refresh"] is True
    assert "refresh_diff" in data


def test_refresh_preserves_cache_when_crawl_is_degraded(httpserver, tmp_path):
    """End-to-end negative control for the truncated-refresh cache clobber:
    a transient per-page failure during a refresh must not replace a
    complete cached bundle, while a definitive 404 deletion must."""
    from werkzeug.wrappers import Response

    base = httpserver.url_for("/")
    state = {"page2": "ok"}

    def page2_handler(_request):  # type: ignore[no-untyped-def]
        if state["page2"] == "ok":
            return Response(
                "<html><head><title>P2</title></head><body><main>Two</main></body></html>",
                content_type="text/html",
            )
        if state["page2"] == "broken":
            return Response(status=500)
        return Response(status=404)

    httpserver.expect_request("/page").respond_with_data(
        "<html><head><title>P1</title></head><body><main>"
        "<a href='/page2'>two</a></main></body></html>",
        content_type="text/html",
    )
    httpserver.expect_request("/page2").respond_with_handler(page2_handler)
    profile = SourceProfile(
        id="degrade",
        name="Degrade",
        base_url=base,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            follow_links=True,
            max_pages=5,
            max_depth=1,
        ),
        targets=(TargetSpec(id="t", name="T", urls=("/page",)),),
    )
    run_profile(profile, output_dir=tmp_path)
    cache_file = next((tmp_path / ".cache" / "bundles").glob("degrade--t-*.json"))
    assert len(json.loads(cache_file.read_text())["bundle"]["pages"]) == 2

    state["page2"] = "broken"
    run_profile(profile, output_dir=tmp_path, refresh=True)
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    assert manifest["refresh_degraded"] == {"t": True}
    assert manifest["refresh_diff"]["t"]["removed"]
    # The cached bundle was not clobbered by the degraded refresh.
    assert len(json.loads(cache_file.read_text())["bundle"]["pages"]) == 2
    state["page2"] = "ok"
    run_profile(profile, output_dir=tmp_path)
    # A plain run after recovery serves the complete cached bundle.
    assert len(json.loads(cache_file.read_text())["bundle"]["pages"]) == 2

    state["page2"] = "gone"
    run_profile(profile, output_dir=tmp_path, refresh=True)
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    assert manifest["refresh_degraded"] == {"t": False}
    # A definitive absence propagates the deletion into the cache.
    assert len(json.loads(cache_file.read_text())["bundle"]["pages"]) == 1
