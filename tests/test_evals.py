"""Fixture evals: hostile-corpus release gates (dated baseline)."""

from __future__ import annotations

import json


from skillarum.evals import evaluate_fixture, write_baseline


def test_baseline_over_real_rendered_skill(rendered_skill, tmp_path):
    report = evaluate_fixture(rendered_skill.parent)
    assert report["evidence_origin"] == "fixture"
    assert report["ok"] is True, report
    baseline = write_baseline(
        [report], tmp_path / "baseline.json", recorded_at="2026-08-30T00:00:00Z"
    )
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["recorded_at"] == "2026-08-30T00:00:00Z"
    for name, gate in payload["gates"].items():
        assert gate["passed"] == gate["total"], name


def test_non_leakage_scan_finds_embedded_token(tmp_path):
    from skillarum.evals import scan_package_for_leaks

    pkg = tmp_path / "leaky"
    pkg.mkdir()
    (pkg / "SKILL.md").write_text("use key ghp_Abcdefghij0123456789 here\n")
    leaks = scan_package_for_leaks(pkg)
    assert leaks and "SKILL.md: api_key_prefix" in leaks[0]


def test_effect_floor_expectation_from_manifest(rendered_skill):
    from skillarum.evals import _corpus_from_manifest
    from skillarum.render import effect_floor

    manifest = json.loads(rendered_skill.parent.joinpath("manifest.json").read_text())
    assert effect_floor(_corpus_from_manifest(manifest)) == manifest["effect"]
