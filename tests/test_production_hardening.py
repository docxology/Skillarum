from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from skillarum.cli import _find_run_manifest, main
from skillarum.crawler import CrawlError, WebsiteCrawler, _retry_after
from skillarum.generators import (
    DeterministicGenerator,
    FallbackGenerator,
    OllamaGenerator,
    UnavailableGenerator,
    generator_for,
)
from skillarum.models import (
    CrawlConfig,
    ExtractionConfig,
    GenerationConfig,
    PreparedCorpus,
    PreparedPage,
    RetryConfig,
    SkillDraft,
    SourceProfile,
    TargetSpec,
)
from skillarum.pipeline import PIPELINE_VERSION, inspect_cache, run_profile
from skillarum.render import render_skill, validate_skill_package
from skillarum.utils import sha256_text


def _corpus(name: str = "Fixture-Skill") -> PreparedCorpus:
    return PreparedCorpus(
        profile_id="fixture",
        profile_name="Fixture Site",
        target_id="page",
        skill_name=name,
        pages=(
            PreparedPage(
                url="https://example.org/page",
                title="Fixture",
                headings=("Intro",),
                text="Source text",
                links=(),
                requested_url="https://example.org/page",
                final_url="https://example.org/page",
                fetched_at="now",
                status_code=200,
                content_sha256=sha256_text("Source text"),
            ),
        ),
    )


def _profile(base_url: str, *, crawl: CrawlConfig | None = None) -> SourceProfile:
    return SourceProfile(
        id="hardening",
        name="Hardening Fixture",
        base_url=base_url,
        crawl=crawl or CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )


def test_generation_config_trace_round_trip_and_auto_contract() -> None:
    config = GenerationConfig.from_mapping(
        {
            "backend": "ollama",
            "ollama_model": "fixture",
            "retry": {
                "max_attempts": 3,
                "base_delay_seconds": 0,
                "max_delay_seconds": 1,
            },
        }
    )
    assert config.with_overrides(model="custom").model == "custom"
    assert config.fingerprint() == config.fingerprint()
    with pytest.raises(ValueError, match="auto"):
        GenerationConfig.from_mapping({"backend": "auto", "fallback_backend": "ollama"})
    with pytest.raises(ValueError, match="credentials"):
        GenerationConfig.from_mapping(
            {"ollama_url": "http://user:secret@localhost:11434"}
        )
    draft = DeterministicGenerator().generate(_corpus())
    restored = SkillDraft.from_payload(draft.to_payload())
    assert restored.trace is not None
    assert restored.trace.selected_backend == "deterministic"
    assert restored.trace.fallback_chain == ("deterministic",)
    assert restored.trace.attempts[0].status == "success"


def test_ollama_retries_transient_http_and_records_trace(ollama_server) -> None:
    base_url, requests = ollama_server
    generator = OllamaGenerator(
        model="retry",
        base_url=base_url,
        retry=RetryConfig(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0),
    )
    draft = generator.generate(_corpus())
    assert len(requests) == 2
    assert draft.trace is not None
    assert len(draft.trace.attempts) == 2
    assert draft.trace.attempts[0].status == "failure"
    assert draft.trace.attempts[0].retries == 0
    assert draft.trace.attempts[1].status == "success"


def test_malformed_provider_output_is_not_retried(ollama_server) -> None:
    base_url, requests = ollama_server
    generator = OllamaGenerator(
        model="invalid-content",
        base_url=base_url,
        retry=RetryConfig(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0),
    )
    with pytest.raises(ValueError) as raised:
        generator.generate(_corpus())
    assert len(requests) == 1
    trace = raised.value.generation_trace
    assert len(trace.attempts) == 1
    assert trace.attempts[0].error_type == "ValueError"


def test_fallback_trace_keeps_primary_attempts() -> None:
    generator = generator_for(
        "ollama",
        ollama_url="http://127.0.0.1:1",
        ollama_timeout_seconds=0.05,
        fallback_backend="deterministic",
        retry=RetryConfig(max_attempts=2, base_delay_seconds=0, max_delay_seconds=0),
    )
    draft = generator.generate(_corpus())
    assert draft.generator == "deterministic"
    assert draft.trace is not None
    assert draft.trace.fallback_used is True
    assert draft.trace.selected_backend == "deterministic"
    assert draft.trace.fallback_chain == ("ollama", "deterministic")
    assert [attempt.backend for attempt in draft.trace.attempts[:2]] == [
        "ollama",
        "ollama",
    ]
    assert [attempt.backend for attempt in draft.trace.attempts][-1] == "deterministic"


def test_fallback_failure_trace_is_attached_to_error() -> None:
    generator = FallbackGenerator(
        UnavailableGenerator("primary", "primary unavailable"),
        UnavailableGenerator("fallback", "fallback unavailable"),
    )
    with pytest.raises(RuntimeError) as raised:
        generator.generate(_corpus())
    assert raised.value.generation_trace is not None
    trace = raised.value.__cause__.generation_trace
    assert trace.selected_backend is None
    assert trace.fallback_used is True
    assert [attempt.backend for attempt in trace.attempts] == ["primary", "fallback"]


def test_fallback_does_not_hide_programming_errors() -> None:
    class BrokenGenerator:
        name = "broken"

        def cache_key(self) -> str:
            return "broken"

        def generate(self, corpus: PreparedCorpus) -> SkillDraft:
            raise AssertionError("implementation defect")

    generator = FallbackGenerator(BrokenGenerator(), DeterministicGenerator())
    with pytest.raises(AssertionError, match="implementation defect"):
        generator.generate(_corpus())

    class RuntimeBroken(BrokenGenerator):
        def generate(self, corpus: PreparedCorpus) -> SkillDraft:
            raise RuntimeError("unexpected implementation failure")

    with pytest.raises(RuntimeError, match="unexpected implementation failure"):
        FallbackGenerator(RuntimeBroken(), DeterministicGenerator()).generate(_corpus())


def test_crawler_streams_oversized_response_and_separates_limits(
    fixture_server: str,
) -> None:
    profile = _profile(
        fixture_server,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_response_bytes=32,
            max_requests=4,
            retry=RetryConfig(max_attempts=1),
        ),
    )
    with WebsiteCrawler(profile) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(TargetSpec(id="large", name="Large", urls=("/stream-large",)))
        assert any("response exceeds" in str(event) for event in crawler.fetcher.events)

    robots_profile = _profile(
        fixture_server,
        crawl=CrawlConfig(
            respect_robots=True,
            allow_private_hosts=True,
            max_pages=1,
            max_requests=2,
            retry=RetryConfig(max_attempts=1),
        ),
    )
    with WebsiteCrawler(robots_profile) as crawler:
        bundle = crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))
        assert len(bundle.pages) == 1
        assert crawler.request_count == 2  # robots + accepted page


def test_crawler_retries_transient_and_records_request_events(
    fixture_server: str,
) -> None:
    profile = _profile(
        fixture_server,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_requests=2,
            retry=RetryConfig(
                max_attempts=2, base_delay_seconds=0, max_delay_seconds=0
            ),
        ),
    )
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(
            TargetSpec(id="transient", name="Transient", urls=("/transient",))
        )
    assert len(bundle.pages) == 1
    assert crawler.request_count == 2
    assert any(event.get("status") == "retrying" for event in bundle.events)


def test_crawler_retry_after_parser_and_rate_limiting(fixture_server: str) -> None:
    assert _retry_after(None) is None
    assert _retry_after("0") == 0
    assert _retry_after("not-a-date") is None
    assert _retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is not None
    profile = _profile(
        fixture_server,
        crawl=CrawlConfig(
            respect_robots=True,
            allow_private_hosts=True,
            min_delay_seconds=0.01,
            max_requests=2,
            retry=RetryConfig(max_attempts=1),
        ),
    )
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))
    received = [event for event in bundle.events if event.get("status") == "received"]
    assert len(received) == 2
    assert datetime.fromisoformat(
        str(received[1]["timestamp"])
    ) >= datetime.fromisoformat(str(received[0]["timestamp"]))


def test_pipeline_state_failure_cache_inspection_and_target_name(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = _profile(fixture_server)

    class WrongNameGenerator:
        name = "wrong-name"

        def generate(self, corpus: PreparedCorpus) -> SkillDraft:
            return SkillDraft(
                name="provider-name",
                description="Wrong name provider",
                body=(
                    "# Provider\n\n## Source boundaries\n\nSource.\n\n"
                    "## Semantic knowledge\n\nSemantics.\n\n## Procedural guidance\n\nProcedure.\n\n"
                    "## Verification\n\nVerify."
                ),
                source_urls=corpus.source_urls,
                generator=self.name,
            )

    paths = run_profile(profile, output_dir=tmp_path, generator=WrongNameGenerator())
    manifest = json.loads((paths[0].parent / "manifest.json").read_text())
    assert manifest["schema_version"] == 2
    assert manifest["skill_name"] == "page"
    assert manifest["requested_skill_name"] == "Page"
    assert manifest["metadata"]["model_suggested_name"] == "provider-name"
    state = json.loads(next((tmp_path / "runs").glob("*/state.json")).read_text())
    assert [item["state"] for item in state["history"]][-1] == "rendered"
    assert [item["state"] for item in state["history"]].count("acquiring") == 1
    assert {
        "planned",
        "acquiring",
        "preparing",
        "generating",
        "validating",
        "rendered",
    }.issubset({item["state"] for item in state["history"]})

    cache = next((tmp_path / ".cache/drafts").glob("*.json"))
    payload = json.loads(cache.read_text())
    payload["draft"]["body"] = "tampered"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / ".cache" / "hardening--stale.json").write_text(
        json.dumps({"pipeline_version": "old", "cache_version": 1}), encoding="utf-8"
    )
    outside_cache = tmp_path / "outside-cache.json"
    outside_cache.write_text(
        json.dumps({"pipeline_version": PIPELINE_VERSION}), encoding="utf-8"
    )
    (tmp_path / ".cache" / "symlink.json").symlink_to(outside_cache)
    report = inspect_cache(tmp_path)
    assert report["counts"]["corrupt"] >= 1
    assert report["counts"]["stale"] >= 1
    assert any(
        item.get("reason") == "symlink cache entry" for item in report["entries"]
    )
    profile_report = inspect_cache(tmp_path, profile=profile)
    assert profile_report["counts"]["stale"] >= 1
    assert all(
        "other-profile--" not in item["path"] for item in profile_report["entries"]
    )


def test_pipeline_persists_failure_manifest(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = _profile(fixture_server)

    class BadGenerator:
        name = "bad"

        def generate(self, corpus: PreparedCorpus) -> SkillDraft:
            return SkillDraft(
                name=corpus.skill_name,
                description="bad",
                body="# missing sections",
                source_urls=corpus.source_urls,
                generator=self.name,
            )

    with pytest.raises(ValueError, match="required sections"):
        run_profile(profile, output_dir=tmp_path, generator=BadGenerator())
    failure = next((tmp_path / "runs").glob("*/failure.json"))
    assert json.loads(failure.read_text())["state"] == "failed"
    state = json.loads(failure.parent.joinpath("state.json").read_text())
    assert state["state"] == "failed"

    class SecretErrorGenerator:
        name = "secret-error"

        def generate(self, corpus: PreparedCorpus) -> SkillDraft:
            raise RuntimeError("Authorization: Bearer top-secret-value")

    with pytest.raises(RuntimeError):
        run_profile(profile, output_dir=tmp_path, generator=SecretErrorGenerator())
    secret_failure = next(
        path
        for path in (tmp_path / "runs").glob("*/failure.json")
        if json.loads(path.read_text())["generator"] == "secret-error"
    )
    secret_payload = json.loads(secret_failure.read_text())
    assert "top-secret-value" not in secret_payload["error"]
    assert "[REDACTED]" in secret_payload["error"]


def test_render_transaction_recovery_and_v1_validation(tmp_path: Path) -> None:
    prepared = _corpus()
    draft = DeterministicGenerator().generate(prepared)
    path = render_skill(draft, prepared, tmp_path / "skills")
    target_dir = path.parent
    backup = target_dir.parent / ".Fixture-Skill.backup-test"
    target_dir.rename(backup)
    render_skill(draft, prepared, tmp_path / "skills")
    assert path.exists()
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 1
    manifest["skill_format"] = "SKILL.md/v1"
    for field in (
        "run_id",
        "cache_identity",
        "generator_fingerprint",
        "generation_trace",
        "request_events",
        "artifact_hashes",
    ):
        manifest.pop(field, None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_skill_package(path)["name"] == "fixture-skill"

    render_skill(draft, prepared, tmp_path / "skills")
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_version"] = 2
    manifest["skill_format"] = "SKILL.md/v2"
    manifest["artifact_hashes"]["SKILL.md"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash"):
        validate_skill_package(path)


def test_v2_package_validation_enforces_trust_and_body_contract(tmp_path: Path) -> None:
    prepared = _corpus()
    bad_draft = SkillDraft(
        name=prepared.skill_name,
        description="Incomplete",
        body="# Incomplete\n\n## Semantic knowledge\n\nOnly semantics.",
        source_urls=prepared.source_urls,
        generator="fixture",
    )
    with pytest.raises(ValueError, match="required sections"):
        render_skill(bad_draft, prepared, tmp_path / "skills")

    path = render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "valid"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["metadata"]["source_bounded"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="source_bounded"):
        validate_skill_package(path)

    render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "valid"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["area"] = "../../Math4Wisdom"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="safe artifact label"):
        validate_skill_package(path)

    render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "valid"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"][0]["content_sha256"] = "not-a-sha256"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="hashes must be SHA-256"):
        validate_skill_package(path)

    render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "valid"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_urls"] = ["https://example.com/other"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="do not match page provenance"):
        validate_skill_package(path)


def test_v2_package_validation_requires_corpus_identity(tmp_path: Path) -> None:
    prepared = _corpus()
    path = render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "skills"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cache_identity"]["corpus_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="expected provenance"):
        validate_skill_package(path, expected_corpus_fingerprint=prepared.fingerprint())


def test_request_events_have_unambiguous_request_semantics(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="telemetry",
        name="Telemetry",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="pages", name="Pages", urls=("/redirect", "/page")),),
    )
    run_profile(profile, output_dir=tmp_path)
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    target = manifest["target_records"][0]
    package = tmp_path / target["package_snapshot"]
    package_manifest = json.loads(package.parent.joinpath("manifest.json").read_text())
    assert package_manifest["request_count"] == sum(
        event.get("request_attempt") is True
        for event in package_manifest["request_events"]
    )
    assert any(
        event.get("kind") == "duplicate" for event in package_manifest["request_events"]
    )
    assert any(
        event.get("kind") == "redirect" and event.get("status") == "redirect"
        for event in package_manifest["request_events"]
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(source_urls=["javascript:unsafe"]), "source URLs"),
        (
            lambda value: value.update(
                source_urls=[value["source_urls"][0], value["source_urls"][0]]
            ),
            "unique",
        ),
        (
            lambda value: value["pages"][0].update(requested_url="javascript:unsafe"),
            "invalid URL",
        ),
        (
            lambda value: value["pages"][0].update(canonical_url="javascript:unsafe"),
            "invalid canonical URL",
        ),
        (lambda value: value["pages"][0].update(fetched_at=""), "retrieval timestamp"),
        (lambda value: value["pages"][0].update(status_code=199), "status code"),
        (lambda value: value["pages"][0].update(status_code=300), "status code"),
        (lambda value: value["pages"][0].update(title=None), "invalid title"),
        (lambda value: value["pages"][0].update(truncated=1), "truncation flag"),
        (
            lambda value: value["pages"][0].update(warnings=[1]),
            "warnings must be strings",
        ),
    ],
)
def test_v2_package_validation_rejects_malformed_provenance(
    tmp_path: Path, mutation, message: str
) -> None:
    prepared = _corpus()
    path = render_skill(
        DeterministicGenerator().generate(prepared), prepared, tmp_path / "skills"
    )
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mutation(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        validate_skill_package(path)


def test_render_rejects_bad_trace_and_index_skips_staging(tmp_path: Path) -> None:
    prepared = _corpus()
    draft = DeterministicGenerator().generate(prepared)
    path = render_skill(draft, prepared, tmp_path / "skills")
    manifest_path = path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["generation_trace"] = {
        "attempts": [{"status": "unknown", "backend": "x", "duration_ms": 0}]
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="generation attempt"):
        validate_skill_package(path)
    render_skill(draft, prepared, tmp_path / "skills")
    staging = path.parent.parent / ".Fixture-Skill.staging-orphan"
    staging.mkdir()
    (staging / "manifest.json").write_text("not json", encoding="utf-8")
    from skillarum.render import write_skill_index

    write_skill_index(tmp_path / "skills")
    assert not (tmp_path / "skills/index.json").read_text().strip() == ""


def test_cli_json_doctor_validate_and_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: Test\ndescription: Test\n---\n\n# Test\n", encoding="utf-8"
    )
    assert main(["validate", "--json", str(skill)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert (
        main(
            ["doctor", "--json", "--no-network", "--output-dir", str(tmp_path / "out")]
        )
        == 0
    )
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["ok"] is True
    assert (
        main(["cache", "inspect", "--json", "--output-dir", str(tmp_path / "out")]) == 0
    )
    cache = json.loads(capsys.readouterr().out)
    assert cache["counts"]["valid"] == 0
    skill.write_text("tampered", encoding="utf-8")
    assert main(["validate", "--json", str(skill)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_run_summary_selects_newest_matching_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    old = runs / "old" / "manifest.json"
    new = runs / "new" / "manifest.json"
    for path, run_id in ((old, "old"), (new, "new")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "pipeline_version": PIPELINE_VERSION,
                    "state": "rendered",
                    "run_id": run_id,
                    "targets": ["output/skills/Page/SKILL.md"],
                }
            ),
            encoding="utf-8",
        )
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    assert (
        _find_run_manifest(tmp_path, [Path("output/skills/Page/SKILL.md")])["run_id"]
        == "new"
    )


def test_cli_doctor_network_profile_and_run_json(
    fixture_server: str,
    ollama_tags_server: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"id: fixture\n"
        f"name: Fixture\n"
        f"base_url: {fixture_server}\n"
        "crawl:\n"
        "  respect_robots: false\n"
        "  allow_private_hosts: true\n"
        "generation:\n"
        "  backend: deterministic\n"
        "targets:\n"
        "  - id: page\n"
        "    name: Page\n"
        "    urls: [/page]\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "doctor",
                "--json",
                "--profile",
                str(profile_path),
                "--ollama-url",
                ollama_tags_server,
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert any(
        check["name"] == "ollama_endpoint" and check["model_present"]
        for check in report["checks"]
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    openai_profile = tmp_path / "openai.yaml"
    openai_profile.write_text(
        profile_path.read_text().replace("backend: deterministic", "backend: openai"),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "doctor",
                "--json",
                "--no-network",
                "--profile",
                str(openai_profile),
                "--output-dir",
                str(tmp_path / "doctor"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["ok"] is False

    auto_profile = tmp_path / "auto.yaml"
    auto_profile.write_text(
        profile_path.read_text().replace("backend: deterministic", "backend: auto"),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "doctor",
                "--json",
                "--no-network",
                "--profile",
                str(auto_profile),
                "--output-dir",
                str(tmp_path / "doctor"),
            ]
        )
        == 0
    )
    auto_report = json.loads(capsys.readouterr().out)
    assert auto_report["ok"] is True
    openai_check = next(
        check
        for check in auto_report["checks"]
        if check["name"] == "openai_configuration"
    )
    assert openai_check["ok"] is True
    assert "note" in openai_check

    output = tmp_path / "output"
    assert (
        main(
            [
                "run",
                "--json",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["ok"] is True
    assert summary["run"]["state"] == "rendered"
    assert main(["index", "--json", "--skills-dir", str(output / "skills")]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_concurrent_identical_cli_runs_are_idempotent(
    fixture_server: str, tmp_path: Path
) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"id: concurrent\nname: Concurrent\nbase_url: {fixture_server}\n"
        "crawl:\n  respect_robots: false\n  allow_private_hosts: true\n"
        "targets:\n  - id: page\n    name: Concurrent-Page\n    urls: [/page]\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    command = [
        sys.executable,
        "-m",
        "skillarum",
        "run",
        "--profile",
        str(profile_path),
        "--output-dir",
        str(output),
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=Path(__file__).parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=30) for process in processes]
    assert all(process.returncode == 0 for process in processes)
    assert all(b"Concurrent-Page/SKILL.md" in stdout for stdout, _ in results)
    assert (output / "skills/Concurrent-Page/SKILL.md").exists()
    assert not list((output / "skills").glob(".*.staging-*"))
    state = json.loads(next((output / "runs").glob("*/state.json")).read_text())
    assert state["state"] == "rendered"
