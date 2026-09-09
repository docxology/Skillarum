# docs/ agent guidance

## Overview

`docs/` is the prose surface of the project: topic documents and the
manuscript source tree under [`manuscript/`](manuscript/). It contains no code
and is never executed. Documentation work here must not change behavior in
[`../src/skillarum/`](../src/skillarum/); if a document and the code disagree,
read the code and fix the document.

## Key concepts

**Two products, one boundary.** Generated `SKILL.md` packages are
source-bounded and untrusted. Citations, comparative interpretation, figures,
and manuscript claims belong only to the research layer. Never move scholarly
interpretation into generated skill output; that boundary is stated in
[`v1-boundary.md`](v1-boundary.md) and enforced by the renderer.

**Claims are ledger-bound.** Every manuscript claim is registered in
[`../data/claims.yaml`](../data/claims.yaml) with a named evidence surface, and
every citation in [`../data/citations.yaml`](../data/citations.yaml). Numbers in
the manuscript are hydrated from an evaluation report rather than typed by hand.
See [`evaluation.md`](evaluation.md) and
[`manuscript/AGENTS.md`](manuscript/AGENTS.md).

**Documentation lives next to what it describes.** Each directory in this
project carries its own `AGENTS.md` and `README.md`. This directory holds only
cross-cutting topics that have no single owning directory.

## File organization

### Orientation and reference

| File | Purpose |
| --- | --- |
| [`tutorial.md`](tutorial.md) | End-to-end walkthrough from clone through `doctor`, `run`, `validate`, and install |
| [`architecture.md`](architecture.md) | The `acquire → prepare → process → parse → render` pipeline, module map, and trust boundaries |
| [`v1-boundary.md`](v1-boundary.md) | Deliberate non-goals, including the scholarly publication boundary |
| [`extending.md`](extending.md) | Extension recipes, change-ownership boundaries, and the frozen-output protocol |

### Operating the tool

| File | Purpose |
| --- | --- |
| [`operations.md`](operations.md) | Provider and context policy, cache and idempotency gates, publication quality gates |
| [`policies.md`](policies.md) | The `security` policy pack, its severity model, and the `verify` exit-code mapping |
| [`install-drift.md`](install-drift.md) | Harness roots, the install workflow, and the read-only drift report |
| [`runtimes.md`](runtimes.md) | `compile_frontmatter` and the `agentskills`, `claude`, and `codex` targets |
| [`mcp.md`](mcp.md) | The `skillarum mcp` stdio server, its bounded tools, resources, prompts, and client configuration |
| [`repo-source.md`](repo-source.md) | Ingesting a local git repository as a second source type |
| [`source-refresh.md`](source-refresh.md) | Empty-cache acquisition, the public HTML inventory, raw archives, and installed-skill replacement |

### Evidence and release

| File | Purpose |
| --- | --- |
| [`evaluation.md`](evaluation.md) | Evidence tiers, statistics policy, and reproducible evaluation/publication commands |
| [`evals.md`](evals.md) | Fixture gates, dated baselines, and how they relate to the evidence tiers |
| [`release-checklist.md`](release-checklist.md) | Invariants, code and safety checks, research and publication gates |
| [`ROADMAP_adoption.md`](ROADMAP_adoption.md) | Adoption roadmap in waves — a planning record, not a description of shipped behavior |
| [`statistics.md`](statistics.md) | The executable statistical policy, interval methods, and independent numerical checks |
| [`figures.md`](figures.md) | Source-bound figures, registry schema, point data, and accessibility |
| [`manuscript-bindings.md`](manuscript-bindings.md) | Parameter injection, caption reuse, numeric-prose validation, binding receipts |
| [`publication.md`](publication.md) | Release identifiers, the reserved version DOI, production Zenodo draft state, and deferred post-review steps |

### Manuscript

[`manuscript/`](manuscript/) holds the paper sources: `config.yaml`,
`preamble.md`, nine numbered body sections (`00_abstract.md` through
`08_reproducibility.md`), `99_references.md`, `references.bib`, and
`MANUSCRIPT_STATUS.md`. Its rules live in
[`manuscript/AGENTS.md`](manuscript/AGENTS.md).

## Rules

- ✅ Verify a command against the code before documenting it, and state the
  working directory. Every command in this tree runs from the project root.
- ✅ Cross-link a new document from both [`README.md`](README.md) and this file.
- ✅ Keep interpretation of results in the manuscript and the ledgers, not in
  generated skill packages.
- ❌ Do not document `output/`. It is generated, disposable, and untracked.
- ❌ Do not restate a directory's own guide here. Fix the doc next to the code.
- ❌ Do not copy the parent template rendering engine into this project.

## Manuscript paths

Research commands default to `docs/manuscript/`. Use `--source-dir` or
`--manuscript-dir` for another tree. `research manuscript --render` hydrates
Markdown and copies its bibliography/configuration; PDF/HTML rendering is a
separate parent-template command.

## See also

- [`README.md`](README.md) — the document index
- [`../AGENTS.md`](../AGENTS.md) — project layer contract and testing rules
- [`../src/skillarum/AGENTS.md`](../src/skillarum/AGENTS.md) — module responsibilities
- [`../tests/AGENTS.md`](../tests/AGENTS.md) — the no-mocks and hermeticity rules
- [`../data/AGENTS.md`](../data/AGENTS.md) — profiles, ledgers, and evidence tiers
- [`../scripts/AGENTS.md`](../scripts/AGENTS.md) — why the wrapper stays thin
- [`../cover/AGENTS.md`](../cover/AGENTS.md) — the publication cover asset

The [comprehensive review record](review-2026-09-07.md) records the source map,
findings, claim disposition, current verification, and remaining limits.

[Source refresh](source-refresh.md) documents empty-cache acquisition, the public
HTML inventory, raw response archives, and replacement of installed skills.

[Manuscript bindings](manuscript-bindings.md) documents parameter injection,
caption reuse, numeric-prose validation, and reconstruction receipts.

[Statistical methods](statistics.md) describes the executable policy and
independent numerical checks. [Figure design](figures.md) describes source-bound
interval plots, point data, and accessibility.

The [agentic and manuscript revision](review-agentic-2026-09-07.md) records the
subsequent methods, figure, binding, MCP, operator-skill, and final verification work.
