# Skillarum manuscript

Parent-template-compatible manuscript sources. Section files hold named
double-brace placeholders; results, reporting parameters, profile tables, and
figure captions are hydrated from their owning contracts at render time.
See [manuscript bindings](../manuscript-bindings.md) for validation and provenance.

## Contents

| File | Role |
| --- | --- |
| `config.yaml` | Paper title, version, cover image, authors, publication metadata, keywords, render formats |
| `preamble.md` | Front matter carried into the rendered document |
| `00_abstract.md` | Abstract |
| `01_introduction.md` | Introduction |
| `02_formal_model.md` | Formal model |
| `03_methodology.md` | Methodology |
| `04_security.md` | Security |
| `05_evaluation.md` | Evaluation |
| `06_case_studies.md` | Case studies |
| `07_related_work.md` | Related work |
| `08_reproducibility.md` | Reproducibility |
| `99_references.md` | References section |
| `references.bib` | BibTeX bibliography (29 entries) |
| `MANUSCRIPT_STATUS.md` | Current drafting status |

`AGENTS.md`, `README.md`, `MANUSCRIPT_STATUS.md`, and `SYNTAX.md` are excluded
from the manuscript content and citation sets.

## Quick start

Run from the project root. `docs/manuscript` is the default source directory.

```bash
uv run --extra research python -m skillarum research build --output-dir output --json
```

For a source-only check, use `research manuscript --evaluation output/reports/evaluation-summary.json` without `--render`. The build hydrates Markdown; the sibling template renders PDF and HTML. Resolved copies belong in
`output/manuscript/`; source files must not be edited with measured values.

## Publication metadata

`config.yaml` identifies Daniel Ari Friedman and ORCID
`0000-0001-6232-9096`, declares a blank DOI with an explicit unassigned
status, and points the parent renderer to `cover/skillarum_cover.png`. The
cover is conceptual artwork rather than empirical evidence; its provenance and
accessibility metadata live in [`../../data/cover.yaml`](../../data/cover.yaml).

## More information

See [AGENTS.md](AGENTS.md) for the token, claim, and figure rules, and
[`../evaluation.md`](../evaluation.md) for evidence tiers and the publication
flow.
