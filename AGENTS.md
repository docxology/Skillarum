# Skillarum agent guidance

Skillarum is a standalone code project.
Its implementation lives in `src/skillarum/`; `scripts/` only dispatches the
package CLI. Keep page acquisition, preparation, generation, and rendering as
separate testable stages.

## Per-directory guidance

Each directory documents itself. Read the one next to the code you are
changing, and fix that file rather than growing this one.

| Directory | Guide |
| --- | --- |
| Package source | [`src/AGENTS.md`](src/AGENTS.md), [`src/skillarum/AGENTS.md`](src/skillarum/AGENTS.md) |
| Entrypoints | [`scripts/AGENTS.md`](scripts/AGENTS.md) |
| Tests | [`tests/AGENTS.md`](tests/AGENTS.md) |
| Inputs and ledgers | [`data/AGENTS.md`](data/AGENTS.md), [`data/sources/AGENTS.md`](data/sources/AGENTS.md), [`data/evaluation/AGENTS.md`](data/evaluation/AGENTS.md) |
| Documentation | [`docs/AGENTS.md`](docs/AGENTS.md), [`docs/manuscript/AGENTS.md`](docs/manuscript/AGENTS.md) |
| Publication asset | [`cover/AGENTS.md`](cover/AGENTS.md) |

`output/` is generated and disposable. Only `output/skills/` (deterministic
packages and `index.json`) is tracked, as reviewable published output; every
other path under `output/` stays untracked and undocumented.

## Layer contract

- `src/skillarum/models.py`, `urls.py`, `config.py`, and `prepare.py` are
  deterministic contracts and transformations, with one deliberate exception:
  `urls.is_public_http_url(..., resolve_dns=True)` performs a live
  `socket.getaddrinfo` lookup as an SSRF safety check. `crawler.py` calls it
  at five sites, four of which pass `resolve_dns=True` and therefore resolve
  DNS. It stays in `urls.py` as a reusable URL-classification predicate rather
  than a `crawler.py`-private helper, not because it is side-effect-free.
- `src/skillarum/crawler.py` owns page acquisition and HTML extraction and is
  the only module that fetches pages over HTTP. `index_profile.py` reads an
  index page only through `WebsiteCrawler.fetch_raw`. The other side-effect
  boundaries are explicit: `generators.py` reaches provider endpoints
  (OpenAI, Ollama) and spawns external command generators;
  `cli.py` issues a live Ollama `/api/tags` request for the `doctor` health
  check unless `--no-network` is given (it still creates `output/` and
  `output/.cache` directories); `serve.py` opens a local read-only listening
  socket; `repo_source.py` runs read-only `git` subprocesses. Nothing else
  touches the network.
- `src/skillarum/generators.py` owns generator backends. OpenAI and Ollama
  are optional at runtime; the deterministic backend must always work without
  credentials, a daemon, or a downloaded model.
- `src/skillarum/render.py` owns portable `SKILL.md` validation and
  provenance manifests.
- `src/skillarum/pipeline.py` owns filesystem stage orchestration.
- `src/skillarum/research.py`, `statistics.py`, `manuscript.py`, `figures.py`,
  and `publication.py` form the research layer; `manuscript.py` consumes
  research records and never acquires pages.
- `scripts/` must remain thin wrappers.

## Testing rules

Tests use local fixture HTTP servers or real subprocesses rather than mock
frameworks. Live website and OpenAI tests are opt-in and must not be required
for the default coverage gate.

Tests must be hermetic from a clean checkout: `output/` is disposable and
ignored, so a test may not read pre-existing generated skills or figures. If a
test needs an artifact, create it in `tmp_path` through the real renderer or
figure writer. Evaluation observations must retain their evidence origin
(`fixture`, `live`, or `unknown`), and schema-2 package snapshots must remain
lineage-bound to the run's `02_prepare` corpus.

Run the default suite with:

```bash
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
```

Before a release or push, also run `ruff check src tests`, `ruff format --check src tests`, compilation, the
research ledger/figure/manuscript validators, the parent signpost checks, and
the Codex skill quick validator over both area namespaces. Treat any live
website or Ollama result as an explicitly dated artifact; never turn a local
fixture observation into live-site evidence.

Do not commit credentials, cached crawl state, run logs, or generated OpenAI
responses. Deterministic skills and the generated discovery index may be
retained as reviewable outputs. Preserve the stable stage contract: use
`--refresh` for acquisition and `--force-process` only when a generator must be
rerun for unchanged input.

The release boundary is deliberately two-layered: generated skills remain
source-bounded and untrusted, while citations, comparative interpretation,
figures, and manuscript claims belong only to the scholarly package. A
provider-generated body must pass the portable section and safety validators;
the deterministic extractor may preserve hostile source wording only as
reference data. Parent-template PDF/HTML rendering is a publication check, not
a reason to copy the parent engine into this project.

For scholarly edits, keep claims in `data/claims.yaml`, sources in
`data/citations.yaml`, and figure provenance in the registry. Quantitative
claims must identify their observation or artifact evidence; fixture results
are never presented as live-site evidence. Run the full clean-checkout suite,
ledger validation, figure validation, manuscript validation, and signpost
checks before publishing a branch.

The manuscript defaults to `docs/manuscript/`; `research build` runs the
offline research stages in dependency order. See
[`docs/manuscript/AGENTS.md`](docs/manuscript/AGENTS.md).

## Codex skill compatibility

The two canonical output namespaces are intentionally human-readable:
`skills/Math4Wisdom/` and `skills/Active-Inference-Institute/`. A target’s
requested name remains authoritative in the manifest, provenance section, and
directory path. The `SKILL.md` frontmatter `name` is a lowercase hyphen-case
portable slug because Codex validates that field as an installable skill name.
Do not flatten the area directories or replace the requested target name in
the manifest. Validate both canonical packages with the local Codex
`skill-creator` quick validator after a live or cached run.

## Current verification

Run the commands in [the release checklist](docs/release-checklist.md). Historical
command checkmarks are not current receipts. Both the development and research
extras are required for the full suite. Source changes are verified with real
negative controls in `tests/test_review_regressions.py`.

`publication.py` owns the ordered offline research build. New generated skills
store effect annotations under `metadata.skillarum_effect`; the manifest retains
`effect` and `effect_floor`. Human ratings are ordinal integers; degenerate kappa
is undefined. Evidence origin is persisted at acquisition and cannot be upgraded
by a later CLI aggregation flag.

Authored investigation skills (currently `skills/math4wisdom-cube/`) carry a
`metadata.version`, a `CHANGELOG.md`, and source/mathematics/interpretation
ledgers; a mathematical claim in one must be recomputed by its own checker
script, which `tests/test_index_profile.py` runs. Investigator reports about a
skill live verbatim under `docs/investigations/`.

The authored operator skill is under `skills/skillarum/`; its own guide explains
the distinction from generated website-derived packages. MCP paths are bounded
to a configured root, with index writes explicitly enabled. See `docs/mcp.md`.
Manuscript binding is owned by `manuscript.py`, numerical policy by `statistics.py`;
`research.py` retains compatibility exports.
