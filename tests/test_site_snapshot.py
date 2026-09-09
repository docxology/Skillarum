"""Real local HTTP snapshots, failed discovery, and crawl-limit controls."""

import json

from urllib.parse import urlparse

import pytest

from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec
from skillarum.site_snapshot import (
    archive_site_snapshot,
    load_snapshot_archives,
    scrape_site,
)


def profile(base_url):
    return SourceProfile(
        id="snapshot",
        name="Snapshot",
        base_url=base_url,
        crawl=CrawlConfig(allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )


def test_snapshot_fresh_crawl_and_raw_hash_receipts(fixture_server, tmp_path):
    result = scrape_site(
        profile(fixture_server),
        tmp_path / "snapshot",
        seed_urls=(fixture_server + "/page",),
    )
    assert result["ok"] and result["complete"]
    assert result["accepted_pages"] == 2
    assert len(list((tmp_path / "snapshot/raw").glob("*.html"))) == 2
    assert result["evidence_origin"] == "fixture"
    with pytest.raises(ValueError, match="empty"):
        scrape_site(
            profile(fixture_server),
            tmp_path / "snapshot",
            seed_urls=(fixture_server + "/page",),
        )


def test_page_limit_is_explicitly_incomplete(fixture_server, tmp_path):
    result = scrape_site(
        profile(fixture_server),
        tmp_path / "snapshot",
        seed_urls=(fixture_server + "/page",),
        max_pages=1,
    )
    assert result["ok"] and not result["complete"]
    assert fixture_server + "/other" in result["unresolved_urls"]
    assert any("page limit" in warning for warning in result["warnings"])


def test_sitemap_sweep_excludes_query_actions(httpserver, tmp_path):
    base = httpserver.url_for("/")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/sitemap.xml").respond_with_data(
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}page</loc></url><url><loc>{base}page?action=edit</loc></url></urlset>',
        content_type="application/xml",
    )
    httpserver.expect_request("/page").respond_with_data(
        "<html><title>Page</title><main>Text</main></html>", content_type="text/html"
    )
    result = scrape_site(
        profile(base), tmp_path, seed_urls=(), sitemap_url=base + "sitemap.xml"
    )
    assert result["complete"] and result["seed_count"] == 1
    assert result["sitemap_sha256"]
    assert result["discovery_events"]


@pytest.mark.parametrize(
    "document,match",
    [
        ("<sitemapindex/>", "expected a URL sitemap"),
        ("<!DOCTYPE urlset><urlset/>", "declarations"),
    ],
)
def test_invalid_sitemap_saves_failed_receipt(httpserver, tmp_path, document, match):
    base = httpserver.url_for("/")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/sitemap.xml").respond_with_data(
        document, content_type="application/xml"
    )
    with pytest.raises(ValueError, match=match):
        scrape_site(
            profile(base), tmp_path, seed_urls=(), sitemap_url=base + "sitemap.xml"
        )
    assert json.loads((tmp_path / "snapshot.json").read_text())["ok"] is False


def test_unsafe_or_empty_seeds_fail_with_receipt(fixture_server, tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        scrape_site(
            profile(fixture_server),
            tmp_path / "empty",
            seed_urls=("https://outside.example/",),
        )
    with pytest.raises(ValueError, match="share"):
        scrape_site(
            profile(fixture_server),
            tmp_path / "external",
            seed_urls=(),
            sitemap_url="https://outside.example/sitemap.xml",
        )


def test_archive_round_trip_and_forged_summary(fixture_server, tmp_path):
    source = tmp_path / "snapshot"
    scrape_site(profile(fixture_server), source, seed_urls=(fixture_server + "/page",))
    archive = tmp_path / "source_archives/site.tar.gz"
    summary = archive_site_snapshot(source, archive)
    assert summary["parsed_html_responses"] == 2
    assert load_snapshot_archives(tmp_path) == (summary,)
    from skillarum.research import build_evaluation_report, manuscript_variables

    variables = manuscript_variables(
        build_evaluation_report(()), site_summaries=(summary,)
    )
    assert "| snapshot | 2 | 2 | 0 |" in variables["SITE_REFRESH_SUMMARY"]
    with pytest.raises(ValueError, match="already exists"):
        archive_site_snapshot(source, archive)
    receipt = archive.with_suffix("").with_suffix(".json")
    summary["accepted_pages"] = 999
    receipt.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="differs"):
        load_snapshot_archives(tmp_path)


def test_archive_rejects_corrupt_raw_response(fixture_server, tmp_path):
    source = tmp_path / "snapshot"
    scrape_site(profile(fixture_server), source, seed_urls=(fixture_server + "/page",))
    next((source / "raw").glob("*.html")).write_bytes(b"substituted response")
    with pytest.raises(ValueError, match="raw response hash"):
        archive_site_snapshot(source, tmp_path / "source_archives/site.tar.gz")


def test_archive_rejects_corrupt_envelope_and_symlink(fixture_server, tmp_path):
    source = tmp_path / "snapshot"
    scrape_site(profile(fixture_server), source, seed_urls=(fixture_server + "/page",))
    archive = tmp_path / "source_archives/site.tar.gz"
    archive_site_snapshot(source, archive)
    archive.write_bytes(b"corrupt archive")
    with pytest.raises(ValueError, match="archive hash"):
        load_snapshot_archives(tmp_path)
    (source / "linked").symlink_to(source / "bundle.json")
    with pytest.raises(ValueError, match="symlinks"):
        archive_site_snapshot(source, tmp_path / "other.tar.gz")


def test_duplicate_canonical_alias_is_resolved(httpserver, tmp_path):
    base = httpserver.url_for("/")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    for route in ("/first", "/alias"):
        httpserver.expect_request(route).respond_with_data(
            f'<html><title>Same</title><link rel="canonical" href="{base}first"><main>Text</main></html>',
            content_type="text/html",
        )
    receipt = scrape_site(
        profile(base), tmp_path / "snapshot", seed_urls=(base + "first", base + "alias")
    )
    assert receipt["complete"] and receipt["accepted_pages"] == 1
    assert receipt["parsed_html_responses"] == 2


def test_snapshot_cli_and_incomplete_exit(fixture_server, tmp_path, capsys):
    from dataclasses import asdict
    import yaml
    from skillarum.cli import main

    config = tmp_path / "profile.yaml"
    config.write_text(yaml.safe_dump(asdict(profile(fixture_server))))
    args = [
        "snapshot-site",
        "--profile",
        str(config),
        "--seed",
        fixture_server + "/page",
        "--json",
    ]
    output = tmp_path / "complete"
    assert main([*args, "--output-dir", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["complete"]
    assert main([*args, "--output-dir", str(output), "--archive-only"]) == 1
    assert "requires --archive" in capsys.readouterr().out
    archive = tmp_path / "source_archives/site.tar.gz"
    assert (
        main(
            [
                *args,
                "--output-dir",
                str(output),
                "--archive-only",
                "--archive",
                str(archive),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main([*args, "--output-dir", str(tmp_path / "limited"), "--max-pages", "1"])
        == 1
    )
    assert not json.loads(capsys.readouterr().out)["complete"]


def test_utf16_sitemap_doctype_is_rejected_end_to_end(httpserver, tmp_path):
    """Negative control for the encoding-dependent byte-sniff bypass: a
    UTF-16 sitemap whose DOCTYPE declares internal entities must be
    rejected at the parser, not expanded."""
    base = httpserver.url_for("/")
    document = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<!DOCTYPE urlset [<!ENTITY e "0123456789">]>\n'
        "<urlset><url><loc>http://probe.invalid/&e;</loc></url></urlset>\n"
    ).encode("utf-16")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/sitemap.xml").respond_with_data(
        document, content_type="application/xml"
    )
    with pytest.raises(ValueError, match="declarations"):
        scrape_site(
            profile(base), tmp_path, seed_urls=(), sitemap_url=base + "sitemap.xml"
        )
    assert json.loads((tmp_path / "snapshot.json").read_text())["ok"] is False


def test_malformed_sitemap_loc_does_not_abort_sweep(httpserver, tmp_path):
    base = httpserver.url_for("/")
    parsed = urlparse(base)
    cred_url = f"http://user:pw@{parsed.hostname}:{parsed.port}/secret"
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/sitemap.xml").respond_with_data(
        f"<urlset><url><loc>{base}page</loc></url>"
        f"<url><loc>{cred_url}</loc></url></urlset>",
        content_type="application/xml",
    )
    httpserver.expect_request("/page").respond_with_data(
        "<html><title>Page</title><main>Text</main></html>", content_type="text/html"
    )
    result = scrape_site(
        profile(base), tmp_path, seed_urls=(), sitemap_url=base + "sitemap.xml"
    )
    assert result["accepted_pages"] == 1
    assert result["invalid_urls"] == [cred_url]
    assert result["complete"] is False


def test_archive_refuses_orphan_raw_responses(fixture_server, tmp_path):
    source = tmp_path / "snapshot"
    scrape_site(profile(fixture_server), source, seed_urls=(fixture_server + "/page",))
    (source / "raw" / ("0" * 64 + ".html")).write_bytes(b"<html>orphan</html>")
    with pytest.raises(ValueError, match="unreferenced"):
        archive_site_snapshot(source, tmp_path / "source_archives/site.tar.gz")


def test_forged_summary_cannot_flip_completeness(fixture_server, tmp_path):
    source = tmp_path / "snapshot"
    scrape_site(
        profile(fixture_server),
        source,
        seed_urls=(fixture_server + "/page",),
        max_pages=1,
    )
    receipt = json.loads((source / "snapshot.json").read_text())
    assert receipt["complete"] is False
    summary = archive_site_snapshot(source, tmp_path / "source_archives/site.tar.gz")
    summary_file = tmp_path / "source_archives" / "site.json"
    forged = dict(summary)
    forged["complete"] = True
    forged["unresolved_urls"] = []
    summary_file.write_text(json.dumps(forged, indent=2))
    with pytest.raises(ValueError, match="archived receipt"):
        load_snapshot_archives(tmp_path)


def test_summary_filename_preserves_multidot_stem(tmp_path):
    from skillarum.site_snapshot import _summary_name

    assert _summary_name("active-inference-institute.tar.gz") == (
        "active-inference-institute.json"
    )
    assert _summary_name("v1.2.tar.gz") == "v1.2.json"
    assert _summary_name("plain") == "plain.json"
