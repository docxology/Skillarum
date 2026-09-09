"""Tests for the validation-gated pack command and pack-level manifests."""

from __future__ import annotations

import json
import zipfile


def test_pack_gated_on_validation(rendered_skill, tmp_path):
    out = tmp_path / "packed.zip"
    code = __import__("subprocess").run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "skillarum",
            "pack",
            str(rendered_skill),
            "--zip",
            str(out),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert code.returncode == 0, code.stderr
    report = json.loads(code.stdout)
    assert report["ok"] is True
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "SKILL.md" in names
    assert "manifest.json" in names
    assert "references/sources.json" in names
    assert "regeneration.json" in names


def test_pack_refuses_invalid_skill(rendered_skill, tmp_path):
    import shutil as _shutil

    bad = tmp_path / "Bad"
    _shutil.copytree(rendered_skill.parent, bad)
    with open(bad / "SKILL.md", "a") as fh:
        fh.write("\ntampered\n")
    code = __import__("subprocess").run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "skillarum",
            "pack",
            str(bad / "SKILL.md"),
            "--zip",
            str(tmp_path / "out.zip"),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert code.returncode == 1
    payload = json.loads(code.stdout)
    assert payload["ok"] is False
    assert "error" in payload


def test_regeneration_manifest_in_pack(rendered_skill):
    regen = json.loads(
        (rendered_skill.parent / "regeneration.json").read_text(encoding="utf-8")
    )
    assert regen["schema"] == "skillarum.regeneration/v1"
    assert regen["backend"] == "deterministic"
    assert regen["requested_skill_name"]
    assert regen["profile_fingerprint"]


def test_sources_map_in_pack(rendered_skill):
    sources = json.loads(
        (rendered_skill.parent / "references" / "sources.json").read_text(
            encoding="utf-8"
        )
    )
    assert sources["schema"] == "skillarum.sources/v1"
    assert sources["sources"]
    first = sources["sources"][0]
    assert first["url"].startswith("https://")
    assert first["fetched_at"]
    assert len(first["content_sha256"]) == 64
