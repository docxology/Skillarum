# data/evaluation/ agent guidance

## Overview

This directory holds the declarative evaluation plan and, when humans produce
them, the rating files that feed Skillarum's research layer. It contains plans
and judgments — never crawl state, never generated observations. Observations
are derived from run manifests under `output/` by `skillarum evaluate`.

## File organization

| File | Kind | Purpose |
| --- | --- | --- |
| `cases.yaml` | tracked plan | The live case matrix: `schema_version: 1` plus seven `cases[]` entries |
| `README.md` | doc | Quick reference |
| `AGENTS.md` | doc | This file |

Rating CSVs (for example `rater-1.csv`, `rater-2.csv`) and JSON adjudication
files are written here by humans when a rating round happens. None are present
in this checkout; do not fabricate them.

## `cases.yaml` schema

Each entry declares: `id`, `label`, `profile_id`, `target_id`, `source`, and
`repetitions`. The seven declared cases are:

| Case id | Profile | Target |
| --- | --- | --- |
| `math-three-minds` | `math4wisdom` | `three-minds` |
| `math-three-minds-exposition` | `math4wisdom` | `three-minds-exposition` |
| `math-minds-research` | `math4wisdom` | `minds-research` |
| `aii-institute-overview` | `active-inference-institute` | `institute-overview` |
| `aii-foundations` | `active-inference-institute` | `institute-foundations` |
| `aii-programs` | `active-inference-institute` | `institute-programs` |
| `aii-projects` | `active-inference-institute` | `institute-projects` |

`profile_id` and `target_id` must match the `id` fields in
[`../sources/`](../sources/). The plan states intent; it does not assert that a
run occurred.

## Usage

Run from the project root.

### Generate a blank rating file

```bash
uv run python -m skillarum research ratings-template \
  --output data/evaluation/rater-1.csv \
  --case math-three-minds --case aii-institute-overview --json
```

`--case` is repeatable and required. Repeat the whole command with a different
`--output` per rater.

### Aggregate observations against the case plan

```bash
uv run python -m skillarum evaluate --output-dir output \
  --cases data/evaluation/cases.yaml --json
```

`--cases` already defaults to `data/evaluation/cases.yaml`.

### Score with two independent rating files

```bash
uv run python -m skillarum evaluate --output-dir output \
  --ratings data/evaluation/rater-1.csv \
  --ratings data/evaluation/rater-2.csv --json
```

### Validate an adjudication against the exact files used

```bash
uv run python -m skillarum research validate \
  --ratings data/evaluation/rater-1.csv \
  --ratings data/evaluation/rater-2.csv \
  --adjudication data/evaluation/adjudication.json --json
```

## Rules

- ✅ Two independent completed rating files are required before agreement is
  reported. Agreement stays pending if the files share no case ids.
- ✅ Substantive judgments carry evidence notes or source URLs.
- ✅ An adjudication names the case, criterion, both rater ids, the final 0–4
  score, the adjudicator id, a rationale, and evidence URLs.
- ❌ Never fill the tracked plan with invented or placeholder scores.
- ❌ Never submit duplicate `(case_id, rater_id)` rows; the CLI rejects them.
- ❌ Never relabel a fixture observation as `live`.

The validator checks that every adjudication refers to actual rows in the
associated rating files. When `--ratings` is omitted for an adjudication check,
the conventional sibling `ratings.csv` is used only as a compatibility fallback.

## See also

- [`README.md`](README.md) — quick reference
- [`../AGENTS.md`](../AGENTS.md) — the data tree as a whole
- [`../sources/AGENTS.md`](../sources/AGENTS.md) — where `profile_id`/`target_id` come from
- [`../../docs/evaluation.md`](../../docs/evaluation.md) — evidence tiers, statistics policy, publication flow
