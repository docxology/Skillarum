# docs/

Prose documentation for Skillarum. Topic documents plus the
manuscript source tree. Code lives in [`../src/skillarum/`](../src/skillarum/);
nothing here is executed.

## Quick start

New to the project, in this order:

1. root [`../README.md`](../README.md) — what Skillarum is and the command reference
2. [`tutorial.md`](tutorial.md) — clone to an installed skill, step by step
3. [`architecture.md`](architecture.md) — the five stages and module responsibilities
4. [`operations.md`](operations.md) — cache, provider, and publication gates

## Document map

| Document | Covers |
| --- | --- |
| [`tutorial.md`](tutorial.md) | End-to-end walkthrough: setup, `doctor`, run, validate, install |
| [`architecture.md`](architecture.md) | `acquire → prepare → process → parse → render`, module map, trust boundaries |
| [`evaluation.md`](evaluation.md) | Evidence tiers, statistics policy, reproducible evaluation and publication commands |
| [`operations.md`](operations.md) | Provider/context policy, cache and idempotency gates, publication quality gates |
| [`statistics.md`](statistics.md) | The executable statistical policy, interval methods, and independent numerical checks |
| [`figures.md`](figures.md) | Source-bound figures, registry schema, point data, and accessibility |
| [`mcp.md`](mcp.md) | The `skillarum mcp` stdio server, its bounded tools, resources, prompts, and client configuration |
| [`release-checklist.md`](release-checklist.md) | Invariants, code and safety checks, research and publication gates |
| [`policies.md`](policies.md) | The `security` policy pack, severity model, verify exit-code mapping |
| [`install-drift.md`](install-drift.md) | Harness roots, install workflow, read-only drift report |
| [`repo-source.md`](repo-source.md) | Local git repository as a second source type |
| [`evals.md`](evals.md) | Fixture gates, dated baselines, relation to the evidence tiers |
| [`manuscript-bindings.md`](manuscript-bindings.md) | Parameter injection, caption reuse, numeric-prose validation, binding receipts |
| [`source-refresh.md`](source-refresh.md) | Empty-cache acquisition, public HTML inventory, raw archives, installed-skill replacement |
| [`extending.md`](extending.md) | Extension recipes, ownership boundaries, frozen-output protocol for multi-agent waves |
| [`v1-boundary.md`](v1-boundary.md) | Deliberate non-goals, including the scholarly publication boundary |
| [`runtimes.md`](runtimes.md) | `compile_frontmatter` and the `agentskills` / `claude` / `codex` targets |
| [`investigations/`](investigations/2026-10-09-cube/README.md) | Dated independent-investigator records for authored skills, reports verbatim |
| [`publication.md`](publication.md) | Release identifiers, the reserved version DOI, production Zenodo draft state, and deferred post-review publication steps |

[`manuscript/`](manuscript/README.md) holds the paper sources: nine numbered
body sections, `99_references.md`, `preamble.md`, `MANUSCRIPT_STATUS.md`,
`config.yaml`, and `references.bib`.

## Key facts

- Every sibling directory carries its own `AGENTS.md` and `README.md`. Fix the
  doc next to the code rather than growing this directory.
- Numbers in the manuscript are hydrated from an evaluation report, never typed
  by hand. See [`manuscript/AGENTS.md`](manuscript/AGENTS.md).
- `output/` is generated and disposable. It is not documented.

## Manuscript paths

Research commands default to `docs/manuscript/`. Use `--source-dir` or
`--manuscript-dir` for another tree. `research manuscript --render` hydrates
Markdown and copies its bibliography/configuration; PDF/HTML rendering is a
separate parent-template command.

## Sibling guides

[`../src/README.md`](../src/README.md) ·
[`../src/skillarum/README.md`](../src/skillarum/README.md) ·
[`../scripts/README.md`](../scripts/README.md) ·
[`../tests/README.md`](../tests/README.md) ·
[`../data/README.md`](../data/README.md) ·
[`../cover/README.md`](../cover/README.md)

## More information

See [`AGENTS.md`](AGENTS.md) for the maintenance rules and what belongs in
which document.

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
