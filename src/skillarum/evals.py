"""Fixture evaluation with release-blocking numeric gates.

Adopted from skillwright's evals/BASELINE pattern: hostile fixture pages run
through the pipeline, then releases gate on measurable invariants - secret
non-leakage, effect-tag correctness, frontmatter validity - recorded as a
dated baseline with evidence origin "fixture".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillarum.models import PreparedCorpus, PreparedPage
from skillarum.redaction import scan_for_secrets
from skillarum.render import effect_floor

BASELINE_SCHEMA = "skillarum.evals-baseline"


def evaluate_fixture(skill_dir: str | Path) -> dict[str, Any]:
    """Gate one rendered fixture package on the release invariants.

    Gates: frontmatter_valid (structural + provenance validation of the
    package on disk), effect_tag_correct (recorded effect equals the
    deterministic floor recomputed from the manifest's page provenance),
    and secret_non_leakage across every published file.
    """
    from .render import validate_skill_package

    package_dir = Path(skill_dir)
    skill_path = package_dir / "SKILL.md"
    errors: list[str] = []

    frontmatter_ok = True
    try:
        validate_skill_package(skill_path)
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(str(exc))
        frontmatter_ok = False

    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    recorded_effect = manifest.get("effect")
    expected_effect = effect_floor(_corpus_from_manifest(manifest))
    effect_ok = recorded_effect == expected_effect

    leaks: list[str] = []
    for file_path in sorted(p for p in package_dir.rglob("*") if p.is_file()):
        text = file_path.read_text(encoding="utf-8", errors="surrogateescape")
        for kind in scan_for_secrets(text):
            leaks.append(f"{file_path.name}: {kind}")

    gates = {
        "frontmatter_valid": frontmatter_ok,
        "effect_tag_correct": bool(effect_ok),
        "secret_non_leakage": not leaks,
    }
    return {
        "schema": BASELINE_SCHEMA,
        "skill": str(skill_path),
        "ok": all(gates.values()),
        "gates": gates,
        "errors": errors,
        "leaks": leaks,
        "recorded_effect": recorded_effect,
        "expected_effect": expected_effect,
        "evidence_origin": "fixture",
    }


def write_baseline(reports: list[dict[str, Any]], path: Path, recorded_at: str) -> Path:
    """Persist a dated baseline scorecard over fixture reports."""
    gate_names = ("secret_non_leakage", "effect_tag_correct", "frontmatter_valid")
    baseline = {
        "schema": BASELINE_SCHEMA,
        "version": 1,
        "recorded_at": recorded_at,
        "evidence_origin": "fixture",
        "skills_evaluated": len(reports),
        "gates": {
            name: {
                "passed": sum(1 for r in reports if r["gates"][name] is True),
                "total": len(reports),
            }
            for name in gate_names
        },
        "ok": all(r["ok"] for r in reports),
        "per_skill": [
            {"skill": r["skill"], "gates": r["gates"], "ok": r["ok"]} for r in reports
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _corpus_from_manifest(manifest: dict[str, Any]) -> PreparedCorpus:
    """Rebuild a minimal corpus view from a rendered manifest (no network)."""
    pages = tuple(
        PreparedPage(
            url=page["url"],
            title=page.get("title", ""),
            headings=(),
            text="",
            links=(),
        )
        for page in manifest.get("pages", [])
    )
    return PreparedCorpus(
        profile_id=manifest.get("profile_id", ""),
        profile_name=manifest.get("profile_name", ""),
        target_id=manifest.get("target_id", ""),
        skill_name=manifest.get("skill_name", ""),
        pages=pages,
        request_count=manifest.get("request_count", 0),
    )


def scan_package_for_leaks(skill_dir: Path) -> list[str]:
    """List secret-shaped tokens surviving in any file of a package."""
    leaks: list[str] = []
    for file_path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        text = file_path.read_text(encoding="utf-8", errors="surrogateescape")
        for kind in scan_for_secrets(text):
            leaks.append(f"{file_path.name}: {kind}")
    return leaks
