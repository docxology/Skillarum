# cover/ agent guidance

## Overview

This directory holds exactly one binary asset: the cover illustration used by
the Skillarum manuscript when the sibling template engine renders PDF and HTML.
It is a *publication* asset, not a pipeline artifact — nothing under
`src/skillarum/` reads it at run time, and it is never produced by a run.

## File organization

| File | Role |
| --- | --- |
| `skillarum_cover.png` | The cover image itself (1024x1536, RGB, PNG) |
| `README.md` | Quick reference |
| `AGENTS.md` | This file |

The image is tracked in git. It is deliberately *not* under `output/`, because
`output/` is disposable and regeneratable while this asset is neither.

## Where it is referenced

- [`../data/cover.yaml`](../data/cover.yaml) — the authoritative metadata
  record: `artifact.path`, `artifact.sha256`, dimensions, format, color mode,
  generator, caption, alt text, and an explicit `data_claim: false`.
- [`../docs/manuscript/config.yaml`](../docs/manuscript/config.yaml) —
  `paper.cover.image: "cover/skillarum_cover.png"`, read by the parent
  template renderer.
- `skillarum research publication` hashes the cover into
  `output/reports/publication-manifest.json` when `--project-root` is supplied.

## Rules

- ✅ If the image is replaced, update `sha256`, `dimensions`, `format`,
  `color_mode`, `caption`, `alt_text`, and `limitations` in
  [`../data/cover.yaml`](../data/cover.yaml) in the same change.
- ✅ Keep `data_claim: false` unless the artwork actually plots measured data.
  It currently does not.
- ❌ Do not describe the cover as evidence, a screenshot, or a performance
  diagram. The `limitations` list in `cover.yaml` says so explicitly and the
  manuscript must not contradict it.
- ❌ Do not add generated figures here. Reproducible figures belong to the
  figure registry under `output/figures/` (see
  [`../docs/evaluation.md`](../docs/evaluation.md)).

## Verification

Run from the project root:

```bash
shasum -a 256 cover/skillarum_cover.png
uv run python -m skillarum research publication \
  --output-dir output --project-root . --json
```

The publication step fails if the recorded hash and the file disagree.

## See also

- [`../data/AGENTS.md`](../data/AGENTS.md) — the ledgers that describe this asset
- [`../docs/manuscript/AGENTS.md`](../docs/manuscript/AGENTS.md) — manuscript rules
- [`../AGENTS.md`](../AGENTS.md) — project layer contract
