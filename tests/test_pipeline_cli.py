from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from skillarum.cli import main
from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec
from skillarum.pipeline import run_profile


def test_pipeline_writes_stage_state_and_reuses_cache(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="fixture",
        name="Fixture Site",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )
    first = run_profile(profile, output_dir=tmp_path)
    second = run_profile(profile, output_dir=tmp_path)
    assert first == second
    assert first[0].exists()
    bundle_cache = next((tmp_path / ".cache/bundles").glob("fixture--page--*.json"))
    assert list((tmp_path / ".cache/drafts").glob("fixture--page--*.json"))
    tampered_bundle = json.loads(bundle_cache.read_text())
    tampered_bundle["bundle"]["pages"][0]["text"] = "tampered"
    bundle_cache.write_text(json.dumps(tampered_bundle), encoding="utf-8")
    assert run_profile(profile, output_dir=tmp_path) == first
    manifests = list((tmp_path / "runs").glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["generator"] == "deterministic"
    assert manifest["targets"] == [str(first[0])]
    assert (
        json.loads((tmp_path / "skills/index.json").read_text())["skills"][0]["path"]
        == "Page/SKILL.md"
    )
    skill_manifest = json.loads((tmp_path / "skills/Page/manifest.json").read_text())
    assert skill_manifest["profile_fingerprint"] == profile.fingerprint()
    run_root = manifests[0].parent
    acquired = json.loads((run_root / "01_acquire/page.json").read_text())
    assert acquired["pages"][0]["text"] != "tampered"
    assert (run_root / "01_acquire/page.json").exists()
    assert (run_root / "02_prepare/page.json").exists()
    assert (run_root / "03_process/page.json").exists()
    assert (run_root / "04_parse/page.json").exists()
    assert (run_root / "05_render/page.json").exists()
    render_state = json.loads((run_root / "05_render/page.json").read_text())
    assert render_state["process_cache_hit"]


def test_cli_validate_returns_status(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: Test\ndescription: Test skill\n---\n\n# Test\n", encoding="utf-8"
    )
    assert main(["validate", str(skill)]) == 0
    assert main(["index", "--skills-dir", str(tmp_path / "skills")]) == 0
    assert (tmp_path / "skills/index.json").exists()


def test_cli_run_and_error_statuses(fixture_server: str, tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"""id: fixture\nname: Fixture\nbase_url: {fixture_server}\ncrawl:\n  respect_robots: false\n  allow_private_hosts: true\ntargets:\n  - id: page\n    name: Page\n    urls: [/page]\n""",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "run",
                "--profile",
                str(profile_path),
                "--target",
                "page",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    assert main(["run", "--profile", str(tmp_path / "missing.yaml")]) == 1


def test_pipeline_rejects_unknown_or_empty_target(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="fixture",
        name="Fixture Site",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )
    with pytest.raises(KeyError, match="unknown"):
        run_profile(profile, output_dir=tmp_path, target_ids=["missing"])
    with pytest.raises(ValueError, match="no targets"):
        run_profile(profile, output_dir=tmp_path, target_ids=[])
    run_profile(profile, output_dir=tmp_path)
    bad_cache = next((tmp_path / ".cache/bundles").glob("fixture--page--*.json"))
    bad_cache.write_text("not json", encoding="utf-8")
    assert run_profile(profile, output_dir=tmp_path)[0].exists()


def test_refresh_reuses_process_for_unchanged_content(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="fixture",
        name="Fixture Site",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Page", urls=("/page",)),),
    )

    class CountingGenerator:
        name = "counting"

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, corpus):
            self.calls += 1
            from skillarum.models import SkillDraft

            return SkillDraft(
                name=corpus.skill_name,
                description="Counting",
                body="# Counting\n\n## Source boundaries\n\nCounting source.\n\n## Semantic knowledge\n\nCounting semantics.\n\n## Procedural guidance\n\nCounting procedure.\n\n## Verification\n\nCounting verification.",
                source_urls=corpus.source_urls,
                generator=self.name,
            )

    generator = CountingGenerator()
    run_profile(profile, output_dir=tmp_path, generator=generator)
    draft_cache = next((tmp_path / ".cache/drafts").glob("fixture--page--*.json"))
    tampered_draft = json.loads(draft_cache.read_text())
    tampered_draft["draft"]["body"] = "# tampered"
    draft_cache.write_text(json.dumps(tampered_draft), encoding="utf-8")
    run_profile(profile, output_dir=tmp_path, refresh=True, generator=generator)
    run_profile(profile, output_dir=tmp_path, force_process=True, generator=generator)
    assert generator.calls == 3


def test_command_backend_runs_through_all_filesystem_stages(
    fixture_server: str, tmp_path: Path
) -> None:
    script = tmp_path / "external_generator.py"
    script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "print(json.dumps({'name': payload['skill_name'], 'description': 'Command', 'body': '# Command\\n\\n## Source boundaries\\n\\nCommand source.\\n\\n## Semantic knowledge\\n\\nCommand semantics.\\n\\n## Procedural guidance\\n\\nCommand procedure.\\n\\n## Verification\\n\\nCommand verification.'}))\n",
        encoding="utf-8",
    )
    profile = SourceProfile(
        id="fixture-command",
        name="Fixture Command",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Command-Page", urls=("/page",)),),
    )
    paths = run_profile(
        profile,
        output_dir=tmp_path / "out",
        backend="command",
        command=[sys.executable, str(script)],
    )
    assert paths[0].exists()
    index = json.loads((tmp_path / "out/skills/index.json").read_text())
    assert index["skills"][0]["generator"] == "command"
    run_manifest = next((tmp_path / "out/runs").glob("*/manifest.json"))
    assert json.loads(run_manifest.read_text())["generator"] == "command"


def test_ollama_backend_falls_back_through_pipeline(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="fixture-ollama",
        name="Fixture Ollama",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Ollama-Page", urls=("/page",)),),
    )
    paths = run_profile(
        profile,
        output_dir=tmp_path / "out",
        backend="ollama",
        fallback_backend="deterministic",
        ollama_url="http://127.0.0.1:1",
        ollama_timeout_seconds=0.2,
    )

    assert paths[0].exists()
    skill_manifest = json.loads(
        (tmp_path / "out/skills/Ollama-Page/manifest.json").read_text()
    )
    assert skill_manifest["generator"] == "deterministic"
    assert skill_manifest["metadata"]["fallback_used"] == "ollama"
    run_manifest = next((tmp_path / "out/runs").glob("*/manifest.json"))
    assert json.loads(run_manifest.read_text())["generator"] == "fallback"
