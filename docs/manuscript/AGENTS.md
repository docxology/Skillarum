# Skillarum manuscript guidance

## Overview

This directory is the manuscript source tree for the Skillarum paper. It is
evidence-first: no measured number is typed into a section file, no claim
stands without a ledger entry, and no figure is drawn by hand. The parent
template checkout renders it; its engine is deliberately not copied here.

## File organization

| File | Role |
| --- | --- |
| `config.yaml` | Paper metadata: title, subtitle, version `0.3.1`, cover image, authors, publication block, keywords, render formats (`pdf` and `html` true) |
| `preamble.md` | Scope and interpretation front matter plus LaTeX preamble |
| `00_abstract.md` … `08_reproducibility.md` | The nine numbered body sections |
| `99_references.md` | References section |
| `references.bib` | BibTeX bibliography, 29 entries |
| `MANUSCRIPT_STATUS.md` | Publication-readiness tracker |
| `README.md`, `AGENTS.md` | Documentation; excluded from the manuscript content set |

The validator and hydrator exclude `AGENTS.md`, `README.md`,
`MANUSCRIPT_STATUS.md`, and `SYNTAX.md`; these operational files are not paper content.

## Hydration tokens

The source configuration enables numeric-prose rejection. Mathematical constants,
citation keys, proper names, and code identifiers remain literal. Author and
publication metadata are explicit declarations in `config.yaml`. Fenced
proposition blocks and labeled equations let the parent renderer own numbering.
The configuration also opts into `require_sec_labels` (every content section
opens with `# Title {#sec:label}`, labels unique) and the offline structural
checks described in [the binding contract](../manuscript-bindings.md):
resolvable cross-references, unique labels, no manual heading numbers, and
balanced `$`/`$$` math delimiters.

## Figures

A section may reference a figure as `output/figures/<name>.svg` or
`.png`. The validator resolves every such reference against
`output/figures/figure_registry.json` and rejects any figure the registry does
not contain. Figures are produced by the project figure registry
(`skillarum figures`), never edited by hand.

## Claims and citations

Claims must correspond to [`../../data/claims.yaml`](../../data/claims.yaml)
and citations to [`../../data/citations.yaml`](../../data/citations.yaml).
Generated skills remain source-bounded: the manuscript may discuss external
literature, but scraped source-page text must never be treated as scholarly
authority without an explicit citation and evidence tier.

## Manuscript paths

Research commands default to `docs/manuscript/`. Use `--source-dir` or
`--manuscript-dir` for another tree. `research manuscript --render` hydrates
Markdown and copies its bibliography/configuration; PDF/HTML rendering is a
separate parent-template command.

## Before publication

Run from the project root:

```bash
uv run python -m skillarum research validate \
  --manuscript-dir docs/manuscript --json
uv run python -m skillarum research manuscript \
  --evaluation output/reports/evaluation-summary.json \
  --source-dir docs/manuscript --render --json
uv run python -m skillarum research publication \
  --output-dir output --project-root . --require-rendered --json
```

## Rules

- ✅ Hydrate every measured value from a token.
- ✅ Register a claim before asserting it; register a citation before citing it.
- ✅ Keep the reserved version DOI `10.5281/zenodo.23271010` in
  `config.yaml` exactly as returned by the Zenodo draft (`doi_status:
  "reserved"`); it registers on publication. The concept DOI was absent
  from the observed draft response — read any concept DOI from an actual
  published response; never derive or blank the reserved identifier.
- ❌ Never edit a source section with a resolved number. Resolved copies belong
  in `output/manuscript/`.
- ❌ Never present the envelope `generated_at` timestamp as a reproducibility
  guarantee. Compare the report id, observation hashes, and publication
  manifest hashes instead.
- ❌ Never copy the parent template engine into this project.

## See also

- [`README.md`](README.md) — file inventory and quick start
- [`../evaluation.md`](../evaluation.md) — evidence tiers and publication flow
- [`../release-checklist.md`](../release-checklist.md) — the release gate
- [`../../data/AGENTS.md`](../../data/AGENTS.md) — the ledgers
- [`../../cover/AGENTS.md`](../../cover/AGENTS.md) — the cover asset
