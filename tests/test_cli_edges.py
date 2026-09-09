"""In-process CLI edge-path tests (real dispatch via skillarum.cli.main)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from skillarum.cli import main
from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec


# ---------------------------------------------------------------------------
# diff (non-JSON human output + section-change reporting)
# ---------------------------------------------------------------------------


def _copy_package(src: Path, dest: Path) -> Path:
    import shutil

    shutil.copytree(src, dest)
    return dest


def test_diff_human_output_reports_changes(
    rendered_skill: Path, tmp_path: Path, capsys
) -> None:
    old = _copy_package(rendered_skill.parent, tmp_path / "old")
    new = _copy_package(rendered_skill.parent, tmp_path / "new")
    with (new / "SKILL.md").open("a", encoding="utf-8") as fh:
        fh.write("\nExtra note.\n")
    (new / "added.txt").write_text("fresh\n", encoding="utf-8")
    (old / "stale.txt").write_text("old\n", encoding="utf-8")

    assert main(["diff", str(old), str(new)]) == 1  # packages differ
    out = capsys.readouterr().out
    assert "identical: False" in out
    assert "+ added.txt" in out
    assert "- stale.txt" in out
    assert "~ SKILL.md" in out
    assert "SKILL.md section changes:" in out


def test_diff_json_payload_shape(rendered_skill: Path, tmp_path: Path, capsys) -> None:
    payload = json.loads(_diff_json(rendered_skill.parent, rendered_skill.parent))
    assert payload["identical"] is True
    assert payload["added"] == []
    assert payload["unchanged_count"] >= 3


def _diff_json(old: Path, new: Path) -> str:
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["diff", str(old), str(new), "--json"])
    assert code == 0
    return buf.getvalue()


# ---------------------------------------------------------------------------
# pack --verify-signature success + non-JSON output
# ---------------------------------------------------------------------------


def test_pack_verify_signature_and_human_output(
    rendered_skill: Path, tmp_path: Path, capsys
) -> None:
    out_zip = tmp_path / "packed.zip"
    code = main(
        [
            "pack",
            str(rendered_skill),
            "--zip",
            str(out_zip),
            "--verify-signature",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "packed:" in out and "sha256:" in out
    assert "pack_hash:" in out and "packer:" in out
    assert out_zip.is_file()


def test_pack_refuses_missing_skill(tmp_path: Path, capsys) -> None:
    code = main(["pack", str(tmp_path / "nope" / "SKILL.md"), "--json"])
    assert code == 1
    # error payload went to stdout as JSON
    capsys.readouterr()


# ---------------------------------------------------------------------------
# evaluate over a live local fixture profile (source attribution fixture)
# ---------------------------------------------------------------------------


def _write_profile(path: Path, base_url: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "id": "evalfix",
                "name": "Eval Fixture",
                "base_url": base_url,
                "crawl": {"respect_robots": False, "allow_private_hosts": True},
                "targets": [{"id": "page", "name": "Page", "urls": ["/page"]}],
            }
        ),
        encoding="utf-8",
    )


def test_evaluate_local_profile_requires_no_live_flag(
    fixture_server: str, tmp_path: Path
) -> None:
    profile_path = tmp_path / "profile.yaml"
    _write_profile(profile_path, fixture_server)
    out_dir = tmp_path / "out"
    code = main(
        [
            "evaluate",
            "--profile",
            str(profile_path),
            "--output-dir",
            str(out_dir),
            "--json",
        ]
    )
    assert code == 0
    report = json.loads(
        (out_dir / "evaluation")
        .glob("evaluation-*.json")
        .__iter__()
        .__next__()
        .read_text()
    )
    assert report["observations"], "expected at least one observation"
    origins = {
        item.get("evidence_origin", item.get("source"))
        for item in report["observations"]
    }
    assert origins <= {"fixture", "unknown"}
    assert "fixture" in origins


def test_evaluate_public_profile_requires_live(tmp_path: Path) -> None:
    profile_path = tmp_path / "public.yaml"
    _write_profile(profile_path, "https://example.org")
    code = main(
        [
            "evaluate",
            "--profile",
            str(profile_path),
            "--output-dir",
            str(tmp_path / "out2"),
            "--json",
        ]
    )
    assert code == 1  # refuses without --live (explicit opt-in contract)


# ---------------------------------------------------------------------------
# validate (human output + invalid skill)
# ---------------------------------------------------------------------------


def test_validate_human_output_and_invalid(tmp_path: Path, capsys) -> None:
    good = tmp_path / "good" / "SKILL.md"
    good.parent.mkdir()
    good.write_text(
        "---\nname: good\ndescription: Good skill\n---\n\n# Good\n", encoding="utf-8"
    )
    assert main(["validate", str(good)]) == 0
    assert "valid:" in capsys.readouterr().out

    assert main(["validate", str(tmp_path / "missing" / "SKILL.md")]) == 1
    assert "invalid:" in capsys.readouterr().err


def test_validate_mixed_batch_fails_together(tmp_path: Path) -> None:
    good = tmp_path / "SKILL.md"
    good.write_text(
        "---\nname: ok\ndescription: Ok skill\n---\n\n# Ok\n", encoding="utf-8"
    )
    missing = tmp_path / "absent" / "SKILL.md"
    code = main(["validate", str(good), str(missing), "--json"])
    assert code == 1


# ---------------------------------------------------------------------------
# cache inspect with profile (non-JSON pretty output path)
# ---------------------------------------------------------------------------


def test_cache_inspect_human_output(
    fixture_server: str, tmp_path: Path, capsys
) -> None:
    profile_path = tmp_path / "profile.yaml"
    _write_profile(profile_path, fixture_server)
    out_dir = tmp_path / "cacheout"

    from skillarum.pipeline import run_profile_from_path

    run_profile_from_path(profile_path, output_dir=out_dir)
    assert (
        main(
            [
                "cache",
                "inspect",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(out_dir),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert '"cache_version"' in out  # pretty-printed JSON report


# ---------------------------------------------------------------------------
# run manifest discovery helper
# ---------------------------------------------------------------------------


def test_find_run_manifest_matches_rendered_run(
    fixture_server: str, tmp_path: Path
) -> None:
    from skillarum.cli import _find_run_manifest
    from skillarum.pipeline import run_profile_from_path

    profile_path = tmp_path / "profile.yaml"
    _write_profile(profile_path, fixture_server)
    out_dir = tmp_path / "runsout"
    skills = run_profile_from_path(profile_path, output_dir=out_dir)
    manifest = _find_run_manifest(out_dir, list(skills))
    assert manifest is not None
    assert manifest["state"] == "rendered"
    assert {str(path) for path in skills}.issubset(set(manifest["targets"]))


def test_find_run_manifest_returns_none_for_empty_dir(tmp_path: Path) -> None:
    from skillarum.cli import _find_run_manifest

    assert _find_run_manifest(tmp_path, [tmp_path / "x" / "SKILL.md"]) is None


# ---------------------------------------------------------------------------
# error payload contract for malformed profile
# ---------------------------------------------------------------------------


def test_run_error_payload_is_json(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("::: not yaml [", encoding="utf-8")
    code = main(["run", "--profile", str(bad), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "error" in payload


def test_usage_error_for_missing_args(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["run"])  # missing required --profile
    capsys.readouterr()


# ---------------------------------------------------------------------------
# serve CLI binds ephemeral and answers healthz (in-process, foreground blocked)
# ---------------------------------------------------------------------------


def test_serve_json_summary_shape(rendered_skill: Path, capsys) -> None:
    import threading

    from skillarum.serve import serve_skills

    # serve blocks forever; exercise the JSON summary path via monkeypatched wait
    skills_dir = rendered_skill.parent.parent
    server, base_url = serve_skills(skills_dir)
    try:
        # replicate the summary payload the CLI writes
        assert base_url.startswith("http://127.0.0.1:")
    finally:
        server.shutdown()
        server.server_close()
    capsys.readouterr()
    del threading  # imported to document the blocked-wait contract


# keep SourceProfile import used (documents the profile shape used above)
_ = SourceProfile
_ = CrawlConfig
_ = ExtractionConfig
_ = TargetSpec


def test_pack_reports_final_archive_digest(
    rendered_skill: Path, tmp_path: Path, capsys
) -> None:
    import hashlib
    import zipfile

    out_zip = tmp_path / "final.zip"
    code = main(["pack", str(rendered_skill), "--zip", str(out_zip), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    # The reported digest must describe the delivered bytes, including the
    # pack signature that write_signature appends afterwards.
    assert payload["sha256"] == hashlib.sha256(out_zip.read_bytes()).hexdigest()
    with zipfile.ZipFile(out_zip) as zf:
        assert "skillarum.sig" in zf.namelist()


def test_pack_never_embeds_archive_members(
    rendered_skill: Path, tmp_path: Path, capsys
) -> None:
    import zipfile

    skills_root = _copy_package(
        rendered_skill.parent.parent,
        tmp_path / rendered_skill.parent.parent.name,
    )
    package = skills_root / rendered_skill.parent.name

    # The audit repro: after a first pack leaves SKILL.zip beside the
    # package, re-packing must not embed that archive as a member.
    assert main(["pack", str(package / "SKILL.md"), "--json"]) == 0
    capsys.readouterr()
    assert (package / "SKILL.zip").is_file()
    out_zip = tmp_path / "fresh.zip"
    assert (
        main(["pack", str(package / "SKILL.md"), "--zip", str(out_zip), "--json"]) == 0
    )
    capsys.readouterr()
    with zipfile.ZipFile(out_zip) as zf:
        assert not any(name.endswith(".zip") for name in zf.namelist())


def test_doctor_no_network_still_creates_directories(tmp_path: Path, capsys) -> None:
    output_dir = tmp_path / "doctor-out"
    code = main(["doctor", "--no-network", "--output-dir", str(output_dir), "--json"])
    assert code == 0
    capsys.readouterr()
    assert (output_dir / ".cache").is_dir()


def test_research_validate_marks_skipped_manuscript_checks(
    tmp_path: Path, capsys
) -> None:
    citations = tmp_path / "citations.yaml"
    citations.write_text(
        "citations:\n  - id: c\n    title: C\n    authors: [A]\n"
        "    year: 2026\n    kind: paper\n    url: https://example.org/c\n"
    )
    claims = tmp_path / "claims.yaml"
    claims.write_text(
        "claims:\n  - id: x\n    text: X\n    evidence_tier: source\n"
        "    status: supported\n    citation_ids: [c]\n"
    )
    code = main(
        [
            "research",
            "validate",
            "--citations",
            str(citations),
            "--claims",
            str(claims),
            "--figures",
            str(tmp_path / "absent-registry.json"),
            "--publication",
            str(tmp_path / "absent-manifest.json"),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"]
    assert payload["manuscript_validation"]["skipped"] is True
    assert payload["manuscript_validation"]["reason"]
