# data/ agent guidance

## Overview

`data/` holds every tracked *input* to Skillarum that a human authors by hand:
declarative source profiles, the scholarly citation and claim ledgers, cover
metadata, and the evaluation case plan. Nothing here is produced by a run.
Everything a run produces belongs under `output/`, which is disposable.

## Directory structure

| Path | Kind | Purpose |
| --- | --- | --- |
| `sources/` | inputs | Declarative crawl/generation profiles (see [`sources/AGENTS.md`](sources/AGENTS.md)) |
| `evaluation/` | inputs | Live-matrix case plan and human rating files (see [`evaluation/AGENTS.md`](evaluation/AGENTS.md)) |
| `citations.yaml` | ledger | External sources with `id`, `title`, `authors`, `year`, `kind`, `url`, `accessed` |
| `claims.yaml` | ledger | Manuscript claims with `id`, `text`, `evidence_tier`, `status`, and either `artifact_paths`, observation ids, or `citation_ids` |
| `cover.yaml` | ledger | Provenance and accessibility metadata for [`../cover/skillarum_cover.png`](../cover/skillarum_cover.png) |
| `README.md` | doc | Quick reference |
| `AGENTS.md` | doc | This file |

## Key concepts

**Evidence tiers.** Every record in `claims.yaml` declares how it is supported.
A `measured` claim names `artifact_paths` or observation ids that exist in the
repository; a `source` claim names `citation_ids` that resolve in
`citations.yaml`. `skillarum research validate` rejects a claim whose evidence
does not resolve.

**Ledgers are not prose.** The manuscript under
[`../docs/manuscript/`](../docs/manuscript/) cites these ids; it does not
restate the evidence inline. Numeric values in the manuscript are hydrated from
an evaluation report, never typed by hand.

**Profiles are not crawl state.** `sources/*.yaml` declares *what* to acquire.
Acquired pages, prepared corpora, drafts, and run manifests live under
`output/runs/` and `output/.cache/`.

## Usage

Run from the project root.

### Validate the ledgers

```bash
uv run python -m skillarum research validate --json
```

Defaults: `--citations data/citations.yaml`, `--claims data/claims.yaml`,
`--figures output/figures/figure_registry.json`,
`--publication output/reports/publication-manifest.json`.

### Validate with manuscript citation coverage

The default manuscript directory is `docs/manuscript`. An explicit override
is supported:

```bash
uv run python -m skillarum research validate \
  --manuscript-dir docs/manuscript --json
```

### Run a profile

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml --backend deterministic
```

## Rules

- ✅ Add a citation before adding a claim that depends on it.
- ✅ Give every quantitative claim a named observation or artifact.
- ✅ Keep the `accessed` date on every retrieved source.
- ❌ Never present a fixture-server observation as live-site evidence.
- ❌ Never place credentials, API keys, or cached crawl state in this tree.
- ❌ Never hand-edit measured numbers into the manuscript instead of the ledger.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `research validate` reports an unresolved claim | `citation_ids` or `artifact_paths` names something absent from disk or from `citations.yaml` |
| `manuscript_citation_count: 0` | Check that the selected manuscript contains citations |
| Bibliography error | A citation id has no matching entry in [`../docs/manuscript/references.bib`](../docs/manuscript/references.bib) |

## See also

- [`README.md`](README.md) — quick reference
- [`sources/AGENTS.md`](sources/AGENTS.md) — profile schema
- [`evaluation/AGENTS.md`](evaluation/AGENTS.md) — case plan and rating schema
- [`../docs/evaluation.md`](../docs/evaluation.md) — evidence tiers and publication flow
- [`../docs/manuscript/AGENTS.md`](../docs/manuscript/AGENTS.md) — manuscript rules
