# Manuscript bindings

`src/skillarum/manuscript.py` owns source-to-text binding. The ordered
`research build` command supplies the verified evaluation report, current
source profiles, executable statistical policy, and validated figure registry.
It writes resolved sections into `output/manuscript/` and the parent renderer
consumes that tree.

## Sources of values

| Value family | Authority |
| --- | --- |
| Counts, rates, telemetry, evidence labels, review status | Evaluation observations and rederived summary |
| Confidence, bootstrap settings, ordinal bounds | `statistics.DEFAULT_POLICY` |
| Package, pipeline, and manifest versions | Their executable module contracts |
| Configured target membership and limits | `data/sources/*.yaml` |
| Figure captions and alternatives | Validated figure registry |
| Website inventories and acquisition windows | Hash-verified source archive receipts |
| Author identity, title, publication date, DOI status | Authored manuscript `config.yaml` |

Publication metadata is an explicit declaration, not an empirical result.
Mathematical constants, source names, citation keys, and stage identifiers
remain literal. Measurements, reporting settings, and configuration-dependent
counts in body prose use exact `{{UPPERCASE_KEY}}` tokens. The token inventory
is maintained in `manuscript.py`; figure tokens use
`FIGURE_<FIGURE_ID_WITH_UNDERSCORES>_CAPTION` or `_ALT`.

The manuscript opts into `manuscript_bindings.forbid_numeric_prose` in its
configuration. The scanner rejects numeric literals outside mathematical,
code, citation, label, and identifier contexts. It complements semantic review;
it cannot determine whether an English phrase such as “several” overstates
its evidence. Malformed and unknown tokens always fail validation.

The manuscript also opts into `manuscript_bindings.require_sec_labels`: every
content section except the preamble must open with `# Title {#sec:label}`, and
section labels must stay unique. Tree validation additionally enforces the
parent template's syntax contract offline: `[@sec:…]`, `[@fig:…]`, `[@eq:…]`,
and formalism-kind references must resolve to labels defined in the tree,
labels must be unique, headings must not carry manual numbers, and `$`/`$$`
math delimiters must balance. Hydration raises a typed error when a section
uses a `FIGURE_*_CAPTION` or `_ALT` token without a figure registry;
source-only checks leave that precondition to the render step.

## Reconstruction evidence

`output/data/manuscript_variables.json` remains the parent-template-compatible
flat value map. `output/data/manuscript_bindings.json` records each value's
source family,
used tokens per section, hashes of inputs and rendered sections,
and its own content hash. The hashed input inventory spans the manuscript
content, evaluation report, companions, profile declarations, figure registry,
archive summaries, and the executable contract modules (manuscript,
statistics, research, figures, pipeline, render, publication, cli, package
init). The build reconstructs the expected text and values
before succeeding, so merely recomputing a receipt hash after changing a value
does not make that value valid.

All input sections and replacements are checked before hydration starts.
Individual file writes are atomic; the complete output tree is not a filesystem
transaction. A successful research build requires every bound section to match,
and concurrent builds are serialized with a local advisory lock. Inputs that
change during a build cause a failed receipt. After changing sources, rebuild
and rerender before relying on a final publication gate.

## Commands

From the Skillarum root:

```bash
uv run --extra research python -m skillarum research build --json
uv run --extra research python -m skillarum research manuscript \
  --evaluation output/reports/evaluation-summary.json \
  --source-dir docs/manuscript --project-root . --render --json
```

The manuscript-only command uses existing report, figure, and archive inputs.
Use the ordered build after implementation or statistical-policy changes.
Neither command acquires pages, fabricates ratings, or renders PDF/HTML.
