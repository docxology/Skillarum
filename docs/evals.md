# Fixture evals and baselines

Fixture evaluation with release-blocking numeric gates
(`src/skillarum/evals.py`): hostile fixture pages run through the pipeline,
then releases gate on measurable invariants recorded as a dated baseline with
evidence origin `fixture`.

## Fixture gates

`evaluate_fixture(skill_dir)` gates one rendered fixture package on three
invariants:

| Gate | What it checks |
| --- | --- |
| `frontmatter_valid` | Structural + provenance validation of the package on disk (`validate_skill_package`) |
| `effect_tag_correct` | The manifest's recorded `effect` equals the deterministic floor recomputed from the manifest's page provenance (no network access) |
| `secret_non_leakage` | No secret-shaped token survives in any file of the published package (`scan_for_secrets` over every file) |

The returned report carries `schema: skillarum.evals-baseline`, `ok`
(all gates), per-gate booleans, recorded vs expected effect, and
`evidence_origin: "fixture"`. `scan_package_for_leaks(skill_dir)` exposes the
leak scan standalone as a list of `"<file>: <kind>"` strings.

## Dated baselines with `write_baseline`

`write_baseline(reports, path, recorded_at)` persists a baseline scorecard
over a list of fixture reports:

```python
from pathlib import Path
from skillarum.evals import evaluate_fixture, write_baseline

reports = [evaluate_fixture(p) for p in sorted(Path("output/skills").rglob("SKILL.md"))]
write_baseline(reports, Path("output/reports/fixture-baseline.json"), recorded_at="2026-08-30")
```

The baseline file records `recorded_at` (the caller-supplied date), aggregate
pass/total counts per gate, an overall `ok`, and a `per_skill` list. The
`recorded_at` field is the dated-baseline evidence convention: a baseline is
a point-in-time snapshot, always carry its date, and compare later runs
against the dated baseline rather than assuming the previous result still
holds.

## Relation to the research evidence tiers

Fixture gates complement the evidence tiers in
[`evaluation.md`](evaluation.md): local fixture-server runs are labeled
`fixture`, explicitly opted-in public acquisitions are labeled `live`, and
offline aggregation without a profile declaration remains `unknown`. Fixture
baselines are release inputs for pipeline behavior; they never upgrade the
evidence origin of a run.
