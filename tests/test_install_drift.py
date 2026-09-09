"""Tests for install manifest + drift detection (read-only)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from skillarum.install import drift_report, harness_roots, install_skill


def test_install_and_clean_drift(rendered_skill, tmp_path):
    manifest = install_skill(rendered_skill, "claude", home=tmp_path)
    assert manifest["schema"] == "skillarum.install-manifest"
    installed = Path(manifest["installed_path"])
    assert installed.is_file()
    report = drift_report(rendered_skill, "claude", home=Path("/tmp/fakehome_missing"))
    assert report["ok"] is False  # no manifest there


def test_drift_clean_after_install(rendered_skill, tmp_path):
    install_skill(rendered_skill, "agents", home=tmp_path)
    report = drift_report(rendered_skill, "agents", home=tmp_path)
    assert report["ok"] is True, report["issues"]
    assert report["issues"] == []


def test_drift_detects_installed_tampering(rendered_skill, tmp_path):
    manifest = install_skill(rendered_skill, "codex", home=tmp_path)
    target = Path(manifest["installed_path"])
    original = target.read_text(encoding="utf-8")
    target.write_text(original + "\ntampered\n", encoding="utf-8")
    report = drift_report(rendered_skill, "codex", home=tmp_path)
    assert report["ok"] is False
    codes = {issue["code"] for issue in report["issues"]}
    assert "installed_skill_drift" in codes


def test_drift_reports_missing_manifest(rendered_skill, tmp_path):
    report = drift_report(rendered_skill, "claude", home=tmp_path)
    assert report["ok"] is False
    assert report["issues"][0]["code"] == "install_manifest_missing"


def test_install_rejects_traversal_name(tmp_path):
    # F17: a frontmatter name with path separators must not move the install
    # destination outside the harness skills root.
    evil = tmp_path / "evil" / "SKILL.md"
    evil.parent.mkdir()
    evil.write_text(
        "---\nname: ../../../Outside\ndescription: traversal probe\n---\nbody\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="portable single-directory"):
        install_skill(evil, "codex", home=tmp_path)
    assert not (tmp_path / "Outside").exists()


def test_drift_reports_invalid_manifest_json(rendered_skill, tmp_path):
    from skillarum.render import validate_skill_file

    install_skill(rendered_skill, "claude", home=tmp_path)
    name = validate_skill_file(rendered_skill)["name"]
    sidecar = tmp_path / ".claude" / "skills" / name / ".skillarum-install.json"
    sidecar.write_text("{not json", encoding="utf-8")
    report = drift_report(rendered_skill, "claude", home=tmp_path)
    assert report["ok"] is False
    assert report["issues"][0]["code"] == "install_manifest_invalid"


def test_drift_reports_manifest_with_missing_fields(rendered_skill, tmp_path):
    from skillarum.render import validate_skill_file

    install_skill(rendered_skill, "claude", home=tmp_path)
    name = validate_skill_file(rendered_skill)["name"]
    sidecar = tmp_path / ".claude" / "skills" / name / ".skillarum-install.json"
    sidecar.write_text(json.dumps({"harness": "claude"}), encoding="utf-8")
    report = drift_report(rendered_skill, "claude", home=tmp_path)
    assert report["ok"] is False
    codes = {issue["code"] for issue in report["issues"]}
    assert "install_manifest_invalid" in codes


def test_drift_reports_installed_symlink(rendered_skill, tmp_path):
    # A symlinked installed file must surface as a stable issue code, not a
    # tree-hash crash.
    manifest = install_skill(rendered_skill, "codex", home=tmp_path)
    installed = Path(manifest["installed_path"])
    outside = tmp_path / "outside-skill.md"
    outside.write_text("outside content", encoding="utf-8")
    installed.unlink()
    installed.symlink_to(outside)
    report = drift_report(rendered_skill, "codex", home=tmp_path)
    assert report["ok"] is False
    codes = {issue["code"] for issue in report["issues"]}
    assert "installed_package_symlink" in codes


def test_drift_reports_canonical_symlink(rendered_skill, tmp_path):
    # Work on a private copy: the canonical package underlying rendered_skill
    # is a session-scoped fixture and must never be mutated here.
    copy_dir = tmp_path / "canonical-copy" / rendered_skill.parent.name
    copy_dir.parent.mkdir(parents=True)
    shutil.copytree(rendered_skill.parent, copy_dir)
    manifest = install_skill(copy_dir / "SKILL.md", "agents", home=tmp_path)
    canonical = Path(manifest["canonical_path"])
    outside = tmp_path / "outside-canonical.md"
    outside.write_text("outside content", encoding="utf-8")
    canonical.unlink()
    canonical.symlink_to(outside)
    report = drift_report(copy_dir / "SKILL.md", "agents", home=tmp_path)
    assert report["ok"] is False
    codes = {issue["code"] for issue in report["issues"]}
    assert "canonical_package_symlink" in codes


def test_unknown_harness_rejected(rendered_skill, tmp_path):
    with pytest.raises(ValueError):
        install_skill(rendered_skill, "unknown", home=tmp_path)


def test_install_cli_end_to_end(rendered_skill, tmp_path):
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "skillarum",
            "install",
            str(rendered_skill),
            "--harness",
            "agents",
            "--home",
            str(tmp_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert Path(payload["installed_path"]).is_file()


def test_install_replaces_existing_portable_slug(rendered_skill, tmp_path):
    from skillarum.render import validate_skill_file

    name = validate_skill_file(rendered_skill)["name"]
    destination = tmp_path / ".codex/skills" / name
    destination.mkdir(parents=True)
    (destination / "obsolete.txt").write_text("old source material")
    manifest = install_skill(rendered_skill, "codex", home=tmp_path)
    assert Path(manifest["installed_path"]).parent == destination
    assert not (destination / "obsolete.txt").exists()
    assert drift_report(rendered_skill, "codex", home=tmp_path)["ok"]


def test_harness_roots_mapping():
    assert harness_roots() == {
        "codex": ".codex/skills",
        "claude": ".claude/skills",
        "agents": ".agents/skills",
    }
