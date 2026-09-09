from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from skillarum.cli import main
from skillarum.crawler import HTTPFetcher, RobotsCache, WebsiteCrawler
from skillarum.models import (
    CrawlConfig,
    ExtractionConfig,
    RetryConfig,
    SourceProfile,
    TargetSpec,
)
from skillarum.render import render_skill, validate_skill_package
from skillarum.generators import DeterministicGenerator
from skillarum.models import PreparedCorpus, PreparedPage
from skillarum.utils import sha256_text


def _profile(base_url: str, **crawl_overrides: object) -> SourceProfile:
    crawl = CrawlConfig(
        respect_robots=False,
        allow_private_hosts=True,
        follow_links=bool(crawl_overrides.pop("follow_links", False)),
        **crawl_overrides,
    )
    return SourceProfile(
        id="edges",
        name="Edges",
        base_url=base_url,
        crawl=crawl,
        extraction=ExtractionConfig(main_selector=None),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )


def test_crawler_transport_content_length_redirect_and_page_limit(
    fixture_server: str,
) -> None:
    profile = _profile(
        fixture_server, max_response_bytes=100, retry=RetryConfig(max_attempts=1)
    )
    with WebsiteCrawler(profile) as crawler:
        with pytest.raises(Exception, match="Content-Length"):
            crawler._request(f"{fixture_server}/bad-length")
        with pytest.raises(Exception, match="Location"):
            crawler.crawl(TargetSpec(id="bad", name="Bad", urls=("/bad-redirect",)))

    profile = _profile(fixture_server, max_pages=1, max_requests=4, follow_links=True)
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))
    assert any("page limit" in warning for warning in bundle.warnings)


def test_crawler_fallback_extraction_and_request_limit(fixture_server: str) -> None:
    profile = _profile(fixture_server, max_requests=1)
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(
            TargetSpec(id="limited", name="Limited", urls=("/page", "/other"))
        )
        assert len(bundle.pages) == 1
        assert any(
            event.get("reason") == "max_requests exceeded" for event in bundle.events
        )

    with WebsiteCrawler(_profile(fixture_server)) as crawler:
        bundle = crawler.crawl(
            TargetSpec(id="fallback", name="Fallback", urls=("/no-main",))
        )
    assert bundle.pages[0].text == "Fallback extraction."


def test_fetcher_transport_and_robots_failures() -> None:
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=100,
            max_requests=2,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=2, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        with pytest.raises(httpx.HTTPError):
            fetcher.fetch("http://127.0.0.1:1/unavailable")
        fetcher.request_count = 0
        robots = RobotsCache()
        assert robots.allowed("http://127.0.0.1:1/page", fetcher, "Skillarum") is False
        assert robots.errors
    finally:
        client.close()


def test_robots_txt_404_treated_as_allow_all(robots_404_server: str) -> None:
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=5,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        assert robots.allowed(f"{robots_404_server}/page", fetcher, "Skillarum") is True
        assert not robots.errors
    finally:
        client.close()


def test_robots_txt_server_error_fails_closed(robots_5xx_server: str) -> None:
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=5,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        assert (
            robots.allowed(f"{robots_5xx_server}/page", fetcher, "Skillarum") is False
        )
        assert any("robots.txt returned HTTP 503" in error for error in robots.errors)
    finally:
        client.close()


def test_robots_txt_redirect_is_followed(robots_redirect_server: str) -> None:
    """A 3xx robots.txt is followed (bounded) rather than failing the crawl."""
    profile = SourceProfile(
        id="edges-redirect",
        name="Redirect",
        base_url=robots_redirect_server,
        crawl=CrawlConfig(respect_robots=True, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector=None),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))
    assert len(bundle.pages) == 1
    assert "Allowed by redirected robots.txt." in bundle.pages[0].text


def test_robots_txt_redirect_limit_fails_closed(robots_redirect_server: str) -> None:
    """A redirect that exceeds the bound is a fail-closed rejection, not an allow-all."""
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=20,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        robots._redirect_limit = 0  # force every redirect over the bound
        assert (
            robots.allowed(
                f"{robots_redirect_server}/page",
                fetcher,
                "Skillarum",
                allow_private=True,
            )
            is False
        )
        assert any("redirect limit exceeded" in error for error in robots.errors)
    finally:
        client.close()


def test_robots_txt_redirect_without_location_fails_closed(
    robots_redirect_missing_location_server: str,
) -> None:
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=5,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        assert (
            robots.allowed(
                f"{robots_redirect_missing_location_server}/page",
                fetcher,
                "Skillarum",
                allow_private=True,
            )
            is False
        )
        assert any("no Location header" in error for error in robots.errors)
    finally:
        client.close()


def test_robots_txt_redirect_to_invalid_target_fails_closed(
    robots_redirect_invalid_target_server: str,
) -> None:
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=5,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        assert (
            robots.allowed(
                f"{robots_redirect_invalid_target_server}/page",
                fetcher,
                "Skillarum",
                allow_private=True,
            )
            is False
        )
        assert any("redirect target is invalid" in error for error in robots.errors)
    finally:
        client.close()


def test_robots_txt_redirect_to_unsafe_host_fails_closed(
    robots_redirect_unsafe_target_server: str,
) -> None:
    """A private redirect target is rejected before any connection is attempted."""
    client = httpx.Client()
    try:
        fetcher = HTTPFetcher(
            client,
            max_response_bytes=10_000,
            max_requests=5,
            min_delay_seconds=0,
            retry=RetryConfig(
                max_attempts=1, base_delay_seconds=0, max_delay_seconds=0
            ),
        )
        robots = RobotsCache()
        assert (
            robots.allowed(
                f"{robots_redirect_unsafe_target_server}/page", fetcher, "Skillarum"
            )
            is False
        )
        assert any("private or unsafe URL" in error for error in robots.errors)
    finally:
        client.close()


def test_cli_text_modes_and_error_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skills = tmp_path / "skills"
    skills.mkdir()
    assert main(["index", "--skills-dir", str(skills)]) == 0
    assert "index.json" in capsys.readouterr().out
    assert main(["cache", "inspect", "--output-dir", str(tmp_path)]) == 0
    assert "counts" in capsys.readouterr().out
    assert main(["doctor", "--no-network", "--output-dir", str(tmp_path)]) == 0
    assert "doctor: ok" in capsys.readouterr().out
    assert (
        main(
            [
                "doctor",
                "--json",
                "--no-network",
                "--ollama-url",
                "http://user:secret@127.0.0.1:11434",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 1
    )
    doctor_error = capsys.readouterr().out
    assert "user:secret@" not in doctor_error
    assert main(["run", "--json", "--profile", str(tmp_path / "missing.yaml")]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_render_manifest_shape_errors(tmp_path: Path) -> None:
    corpus = PreparedCorpus(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name="T",
        pages=(
            PreparedPage(
                url="https://example.org",
                title="P",
                headings=(),
                text="text",
                links=(),
                requested_url="https://example.org",
                final_url="https://example.org",
                fetched_at="now",
                status_code=200,
                content_sha256=sha256_text("text"),
            ),
        ),
    )
    path = render_skill(
        DeterministicGenerator().generate(corpus), corpus, tmp_path / "skills"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("cache_identity")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        validate_skill_package(path)
    manifest["cache_identity"] = {}
    manifest["generation_trace"] = {
        "attempts": [{"backend": "x", "duration_ms": "bad", "status": "success"}]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="attempt fields"):
        validate_skill_package(path)
    manifest_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        validate_skill_package(path)


def test_render_manifest_integrity_fields_are_strict(tmp_path: Path) -> None:
    corpus = PreparedCorpus(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name="T",
        pages=(
            PreparedPage(
                url="https://example.org",
                title="P",
                headings=(),
                text="text",
                links=(),
                requested_url="https://example.org",
                final_url="https://example.org",
                fetched_at="2026-01-01T00:00:00+00:00",
                status_code=200,
                content_sha256=sha256_text("text"),
            ),
        ),
    )

    def check(mutator, message: str, *, provider: bool = False) -> None:
        draft = DeterministicGenerator().generate(corpus)
        if provider:
            draft = type(draft)(
                name=draft.name,
                description=draft.description,
                body=draft.body.replace("Fixture source", "rm -rf /"),
                source_urls=draft.source_urls,
                generator="provider",
                metadata=draft.metadata,
                trace=draft.trace,
            )
        path = render_skill(draft, corpus, tmp_path / message.replace(" ", "-"))
        manifest_path = path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mutator(manifest)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            validate_skill_package(path)

    check(lambda value: value.__setitem__("request_events", {}), "request events")
    check(lambda value: value.__setitem__("request_count", True), "request count")
    check(lambda value: value.__setitem__("metadata", []), "skill metadata")
    check(lambda value: value.__setitem__("warnings", {}), "skill warnings")
    check(
        lambda value: value.__setitem__("generator_fingerprint", "bad"),
        "generator fingerprint",
    )
    check(
        lambda value: value["metadata"].__setitem__("source_bounded", False),
        "source_bounded",
    )
    check(
        lambda value: value["metadata"].__setitem__("untrusted_source", False),
        "untrusted_source",
    )
    check(
        lambda value: value["metadata"].__setitem__("provenance_binding", "free-form"),
        "provenance",
    )
    check(
        lambda value: value["cache_identity"].__setitem__("corpus_fingerprint", "bad"),
        "corpus fingerprint",
    )
    check(
        lambda value: value["pages"][0].__setitem__("status_code", 302), "status code"
    )
    check(
        lambda value: value["pages"][0].__setitem__("canonical_url", "not-url"),
        "canonical URL",
    )
    check(
        lambda value: value["pages"][0].__setitem__("truncated", "yes"),
        "truncation flag",
    )
    check(
        lambda value: value["pages"][0].__setitem__("warnings", [1]),
        "warnings must be strings",
    )


def test_render_path_authority_and_portable_name_validation(tmp_path: Path) -> None:
    """The validator rejects area and requested-target identity drift vs package path."""
    corpus = PreparedCorpus(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name="Affected",
        area="Alpha",
        pages=(
            PreparedPage(
                url="https://example.org",
                title="P",
                headings=(),
                text="text",
                links=(),
                requested_url="https://example.org",
                final_url="https://example.org",
                fetched_at="2026-01-01T00:00:00+00:00",
                status_code=200,
                content_sha256=sha256_text("text"),
            ),
        ),
    )
    path = render_skill(
        DeterministicGenerator().generate(corpus), corpus, tmp_path / "skills"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    unsafe_area = dict(manifest)
    unsafe_area["area"] = "../escape"
    manifest_path.write_text(json.dumps(unsafe_area), encoding="utf-8")
    with pytest.raises(ValueError, match="safe artifact label"):
        validate_skill_package(path)

    mismatched_area = dict(manifest)
    mismatched_area["area"] = "Beta"
    manifest_path.write_text(json.dumps(mismatched_area), encoding="utf-8")
    with pytest.raises(ValueError, match="area does not match package path"):
        validate_skill_package(path)

    mismatched_name = dict(manifest)
    mismatched_name["requested_skill_name"] = "Something-Else"
    manifest_path.write_text(json.dumps(mismatched_name), encoding="utf-8")
    with pytest.raises(
        ValueError, match="requested target name does not match package path"
    ):
        validate_skill_package(path)

    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_skill_package(path)


def _render_corpus(
    skill_name: str = "Affected", *, area: str = "Alpha"
) -> PreparedCorpus:
    return PreparedCorpus(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name=skill_name,
        area=area,
        pages=(
            PreparedPage(
                url="https://example.org",
                title="P",
                headings=(),
                text="text",
                links=(),
                requested_url="https://example.org",
                final_url="https://example.org",
                fetched_at="2026-01-01T00:00:00+00:00",
                status_code=200,
                content_sha256=sha256_text("text"),
            ),
        ),
    )


def test_render_manifest_schema_identity_and_trace_rejections(tmp_path: Path) -> None:
    """The package validator rejects schema, identity, and trace drift."""
    corpus = _render_corpus()
    path = render_skill(
        DeterministicGenerator().generate(corpus), corpus, tmp_path / "skills"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def tamper(**changes: object) -> dict:
        merged = dict(manifest)
        merged.update(changes)
        manifest_path.write_text(json.dumps(merged), encoding="utf-8")
        return merged

    def expect(fragment: str) -> None:
        with pytest.raises(ValueError, match=fragment):
            validate_skill_package(path)

    tamper(schema_version=99)
    expect("unsupported skill manifest schema")

    tamper(skill_name="wrong-name")
    expect("does not match frontmatter")

    tamper(portable_name="Not a Slug!")
    expect("not Codex-compatible")

    tamper(requested_skill_name="   ")
    expect("requested target name is empty")

    tamper(artifact_hashes=[])
    expect("artifact hashes must be a mapping")

    tamper(cache_identity=[])
    expect("cache identity must be a mapping")

    tamper(source_urls="https://example.org")
    expect("provenance fields must be lists")

    tamper(generation_trace="not-a-trace")
    expect("invalid generation trace")

    tamper(
        generation_trace={
            "attempts": manifest["generation_trace"]["attempts"],
            "fallback_chain": "x",
        }
    )
    expect("invalid generation fallback chain")

    tamper(**{"pages": [dict(manifest["pages"][0], canonical_url="")]})
    expect("invalid canonical URL")

    # restore a pristine manifest and confirm the package is valid again
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_skill_package(path)


def test_render_existing_manifest_unreadable_and_symlink(tmp_path: Path) -> None:
    """A corrupt on-disk manifest and a symlinked manifest are both rejected."""
    corpus = _render_corpus()
    skills = tmp_path / "skills"
    path = render_skill(DeterministicGenerator().generate(corpus), corpus, skills)
    manifest_path = path.parent / "manifest.json"

    # Re-render with a corrupt existing manifest must fail closed, not overwrite.
    manifest_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="existing skill manifest is unreadable"):
        render_skill(DeterministicGenerator().generate(corpus), corpus, skills)
    manifest_path.write_text(
        json.dumps(json.loads("{}") if False else {}), encoding="utf-8"
    )
    # rebuild a valid manifest by re-rendering to a fresh dir
    fresh = tmp_path / "fresh"
    fresh_path = render_skill(DeterministicGenerator().generate(corpus), corpus, fresh)
    fresh_manifest = fresh_path.parent / "manifest.json"
    os.unlink(fresh_manifest)
    os.symlink(tmp_path / "elsewhere.json", fresh_manifest)
    (tmp_path / "elsewhere.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a regular file"):
        validate_skill_package(fresh_path)


def test_validate_skill_file_rejects_bad_yaml_and_non_mapping(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad-yaml.md"
    bad_yaml.write_text(
        "---\nname: [unclosed\ndescription: x\n---\n# Body\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="invalid skill frontmatter"):
        validate_skill_package(bad_yaml)
    not_mapping = tmp_path / "not-mapping.md"
    not_mapping.write_text("---\n- one\n- two\n---\n# Body\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a mapping"):
        validate_skill_package(not_mapping)
