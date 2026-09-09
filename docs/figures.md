# Publication figures

The figure layer (`src/skillarum/figures.py`) turns a persisted evaluation
report into deterministic publication figures, a machine-readable point-data
sidecar, and an auditable registry. It is deterministic: the same report bytes
produce byte-identical artifacts on the same machine.

This page documents what each figure shows, the statistics policy captions
must state, and the registry contract that the manuscript consumes. Generate
figures only through the real writer; never edit an SVG, PNG, sidecar, or
registry by hand.

## Commands

From the project root:

```bash
uv run --extra research python -m skillarum figures \
  --evaluation output/reports/evaluation-summary.json \
  --output-dir output/figures --json
```

To inspect or test a candidate rendering without touching the canonical
surface, write to a temporary directory instead:

```bash
uv run --extra research python -m skillarum figures \
  --evaluation output/reports/evaluation-summary.json \
  --output-dir /tmp/figure-preview --json
```

`generate_figures(report, output_dir, source_data=...)` fails closed unless
`source_data` is the persisted form of the passed report: it must parse as the
report envelope, carry the same `report_id`, and its `artifact_sha256` must
match both its own payload body and the in-memory report content. A stale,
altered, or divergent source file is rejected before anything is plotted.

| Figure ID | Kind | Shows | Eligible denominators |
| --- | --- | --- | --- |
| `pipeline-trust-boundaries` | structural | Five-stage dataflow and the source-data trust boundary | not applicable |
| `run-state-machine` | structural | Persisted run lifecycle and the recoverable failure state | not applicable |
| `cache-integrity-flow` | structural | Hash-dependency chain from configuration to index | not applicable |
| `acquisition-funnel` | empirical | Accepted/rejected/redirected/canonicalized/duplicate/truncated outcomes per area | separate within-area sums; categories are not additive |
| `provider-fallback-outcomes` | empirical | Fallback observations, provider failures, retry attempts per backend | observation-level indicator vs attempt-level counters |
| `generation-latency` | empirical | Persisted generation duration per observation, N/A when telemetry is missing | one value per completed observation |
| `provenance-completeness` | empirical | Observations passing provenance, section, and untrusted-source checks | passing observations out of all completed observations |
| `proportion-intervals` | empirical | Exact binomial intervals for reported proportions, one row per proportion | per-row: completed observations, observations with fallback telemetry, or observed source pages |
| `coverage-truncation` | empirical | Area mapping and truncation percentages | mapping: observed source pages; truncation: accepted pages |
| `request-pressure` | empirical | Recorded request attempts per accepted page per area | total requests divided by accepted pages |
| `area-catalog` | empirical | Table of targets, observations, pages, truncation, and mapping per area | mapping: complete pages over observed source pages |
| `source-overlap` | empirical (gated) | Exact shared accepted-page URLs between every pair of targets; emitted only when at least two observations carry a persisted `source_urls` list | shared URLs out of each target's accepted-page URL list |
| `human-review-rubric` | empirical (gated) | Mean ordinal 0-4 rubric scores; only emitted when two raters have paired cases | rating rows per criterion |

Structural diagrams are contract-derived and carry no empirical claim; they
retain the report context only as metadata, and their captions lead with
"generated from implementation contracts, not from the report's measurements".
`manuscript_refs` lists the manuscript sections that reference a figure via
`@fig:<id>` (verified against `docs/manuscript/`). One declared exception,
recorded here and in the registry entry itself: `source-overlap` is emitted
with the canonical report and its ref points at `05_evaluation`, whose prose
describes the panel conditionally, but the manuscript does not embed it this
wave — a hard caption token plus image include would fail
`validate_manuscript_tree` against the one-observation fixture registries.
The embed lands in a coordinated follow-up (a second fixture target carrying
`metadata.source_urls`, then the five-line embed in `05_evaluation.md`);
until then the registry entry states the prose-only linkage in its
limitations.

## Statistics policy in figures

- Every empirical figure is descriptive. Captions state the population, unit,
  aggregation, denominators, uncertainty policy, and what the figure cannot
  establish. The registry validator rejects captions without `n=` and without
  an interpretation boundary, and it rejects alt text that begins as a
  mid-sentence fragment (a description must start a sentence).
- Every registry entry carries an explicit `denominator`. Structural records
  use the contract-derived default; empirical records state their own
  eligible denominator, matching the table above.
- Count axes use whole-number ticks whenever every plotted value is a whole
  number, and percent axes never suggest a value above 100 (the axis is
  capped at 100 with label headroom). A measured zero is drawn as a visible
  baseline marker in both the hand-drawn fallback SVGs and the Matplotlib
  companions; unavailable telemetry is labelled N/A and never drawn as zero.
- `proportion-intervals` reuses the report's own proportion records verbatim
  (successes, total, rate, exact Clopper-Pearson interval). It never
  recomputes statistics. Each row states its eligible denominator beside its
  label because the denominators differ across rows; rows are not compared
  inferentially.
- `generation-latency` orders its rows by declared source area and then
  target, so observations from the same area are grouped; each value stays
  bound to its own observation.
- `source-overlap` computes exact set intersections of the persisted
  `metadata.source_urls` lists. It is dependence evidence for the interval
  caveats, not a similarity metric between generated skills; targets without
  a recorded list are shown as N/A, not zero.

## Registry contract

`figure_registry.json` is schema 4. Each entry carries:

- Required: `figure_id`, `path` (canonical artifact; the PNG when a raster
  twin exists), `caption`, `alt_text`, `source_data`, `source_sha256`,
  `artifact_sha256`, `sample_size`, plus the v3 fields `title`, `units`,
  `aggregation`, `sample_size_basis`, `generator`, `uncertainty`,
  `limitations`, `manuscript_refs`, and the v4 field `evidence_origin`.
- Optional (validated when present, absent in older registries):
  - `report_id` — the report identity the figure was generated from.
  - `denominator` — the eligible denominator(s) for the plotted quantities.
  - `data_path` / `data_sha256` — a hash-bound point-data sidecar under
    `figure_data/` carrying the plotted rows (labels, values, successes,
    totals, intervals, denominator basis). The validator checks the sidecar's
    relative path, bytes, `figure_id`, and `source_sha256` binding, so a
    sidecar from another report fails validation instead of silently
    decorating the entry.
  - `vector_path` / `vector_sha256` — the SVG original when a raster twin is
    canonical.
- Each entry also has a `label` (`fig:<figure_id>`) for pandoc-crossref.
- `figure_registry.manifest.json` hashes the registry and each artifact.
- Provenance references are generation-root-relative: the writer records the
  evaluation report as `evaluation/<report-id>.json` and the manifest records
  the registry as `figures/figure_registry.json`, both relative to the
  generation root that contains `figures/` and its `evaluation/` sibling.
  This form resolves identically in the checkout and inside a research
  archive whose member root is the generation root. The validator resolves
  references against the registry directory, the generation root, and the
  working directory, and rejects absolute or `..`-traversing references
  fail-closed.

The parent template consumes registry captions as `FIGURE_<ID upper snake
case>_CAPTION` manuscript tokens and resolves `output/figures/<file>`
references against the registry's canonical paths. Captions are therefore
publication-ready prose: they name denominators explicitly and end with the
figure's limits of interpretation. `alt_text` is a separate, visual
description of the plot, not a caption restatement; the validator rejects an
alt text that duplicates the caption and one that begins as a lowercase
mid-sentence fragment, because a screen reader would otherwise announce an
orphaned clause.

## Accessibility and determinism

- Every SVG — hand-drawn fallback and renderer output alike — carries
  `role="img"`, `aria-labelledby`, `<title>`, and `<desc>`; renderer SVGs are
  post-processed to add them. Text is kept as text (`svg.fonttype: none`), so
  direct value labels remain selectable and searchable.
- The palette is Okabe-Ito-based with dark outlines and direct labels; a
  single-series chart uses one hue, and color encodes series identity only in
  grouped charts. Grouped-chart legends sit above the axes so they cannot
  cover bar value labels; matrix cells print their counts so the figure stays
  readable in grayscale.
- Raster companions are 300-dpi PNGs with fixed metadata and no timestamps;
  Matplotlib SVG companions use a fixed hash salt. Two runs over the same
  report produce identical bytes for every artifact, the manifest included,
  because provenance references are generation-root-relative.

## Validation

```bash
uv run python -m skillarum figures \
  --evaluation output/reports/evaluation-summary.json --json
```

The command validates the generated registry (hashes, paths, symlinks,
captions, alt text, bindings) and fails non-zero on any error. Regression
coverage for these guarantees lives in `tests/test_figure_quality.py`;
figure-count and pipeline integration live in `tests/test_scholarship.py`.
