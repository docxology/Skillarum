# Skillarum

Skillarum turns selected public website pages into portable `SKILL.md`
documents for agent harnesses such as Codex, Claude Code, and Hermes.

**Agent orientation (read in this order):** [AGENTS.md](AGENTS.md) (layer
contract + testing rules) → [TODO.md](TODO.md) (backlog with acceptance
lines) → `uv run python -m skillarum doctor --profile
data/sources/math4wisdom.yaml --no-network --json` (one-command health) →
`output/skills/index.json` (discovery index for rendered skills; rebuild with
`uv run python -m skillarum index --skills-dir output/skills`).
On a fresh checkout `output/` does not exist yet: `doctor` creates `output/`
and `output/.cache` even with `--no-network`, and `index.json` appears after
the first `run` or `index` invocation.

It separates the work into five inspectable stages:

```text
acquire → prepare → process → parse → render
```

Acquired page records and prepared corpora are written under `output/runs/`;
configuration-aware page bundles and generator drafts are cached under
`output/.cache/`. Run and artifact identities are stable, so repeating the same
invocation updates the same state instead of creating timestamped duplicates.
The rendered skills directory also contains `index.json` for harness discovery.

## Install

Skillarum requires Python 3.10+. Install from the public repository; a
source checkout also provides the bundled source profiles used below:

```bash
git clone https://github.com/docxology/Skillarum
cd Skillarum
uv sync --extra dev --extra research
```

Optional extras: add `--extra llm` for the OpenAI backend or `--extra
research` for evaluation figures.

## Repository layout

Every directory below carries its own `AGENTS.md` (detailed guide) and
`README.md` (quick reference).

| Directory | Contents |
| --- | --- |
| [`src/`](src/README.md) | Packaging root — src-layout |
| [`src/skillarum/`](src/skillarum/README.md) | The whole implementation: the implementation modules, no subpackages |
| [`scripts/`](scripts/README.md) | Thin CLI wrappers and the parent-render hydration hook |
| [`tests/`](tests/README.md) | pytest modules plus `conftest.py`, no mock frameworks |
| [`data/`](data/README.md) | Hand-authored inputs: profiles, ledgers, cover metadata |
| [`data/sources/`](data/sources/README.md) | The two declarative source profiles |
| [`data/evaluation/`](data/evaluation/README.md) | Case plan and human rating files |
| [`docs/`](docs/README.md) | Architecture, operations, policies, tutorial, roadmap |
| [`docs/manuscript/`](docs/manuscript/README.md) | Manuscript sources and bibliography |
| [`cover/`](cover/README.md) | The manuscript cover image |
| `output/` | Generated and disposable; not documented and not tracked |

## Quick start

From a source checkout:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend deterministic
```

This renders `output/skills/Math4Wisdom/Three-Minds/SKILL.md`.

Render the initial Active Inference Institute bundle with:

```bash
uv run python -m skillarum run \
  --profile data/sources/active_inference_institute.yaml \
  --backend deterministic
```

Use `--refresh` to fetch new source pages instead of using the acquired bundle
cache. If refreshed content is unchanged, the expensive process-stage draft is
still reused. Use `--force-process` to rerun the selected generator, and
`--target <id>` to select one named target from a profile.

Rebuild the discovery index independently with:

```bash
uv run python -m skillarum index --skills-dir output/skills
```

The `doctor` command checks profile validity, output/cache writeability, the
Ollama `/api/tags` endpoint and configured model, and OpenAI configuration when
the selected profile needs it. Use `--no-network` for local-only checks:

~~~bash
uv run python -m skillarum doctor --profile data/sources/math4wisdom.yaml --output-dir output --json
uv run python -m skillarum cache inspect --output-dir output \
  --profile data/sources/math4wisdom.yaml --json
~~~

## Command reference

| Command | Purpose | Details |
| --- | --- | --- |
| `run` | Crawl targets and render skills | (this README) |
| `validate` | Validate one or more `SKILL.md` files | (this README) |
| `verify` | Round-trip a rendered skill through all validators; `--policy security` applies the security policy pack | [`docs/policies.md`](docs/policies.md) |
| `install` | Install a validated package into a harness skills root | [`docs/install-drift.md`](docs/install-drift.md) |
| `drift` | Read-only installed-vs-canonical drift report | [`docs/install-drift.md`](docs/install-drift.md) |
| `pack` | Package a validated skill directory as a zip | (this README) |
| `diff` | Compare two rendered packages at hash and section level | (this README) |
| `index` | Rebuild the discovery index | (this README) |
| `serve` | Read-only HTTP discovery over rendered skills | (this README) |
| `cache inspect` | Inspect cache integrity | (this README) |
| `snapshot-site` | Capture a fresh public HTML inventory with raw receipts | [`docs/source-refresh.md`](docs/source-refresh.md) |
| `doctor` | Profile/output/Ollama/OpenAI health checks | (this README) |
| `evaluate` / `figures` | Research evaluation and figures | [`docs/evaluation.md`](docs/evaluation.md) |
| `research …` | Scholarly validation, ratings, manuscript, publication | [`docs/evaluation.md`](docs/evaluation.md) |
| `mcp` | Root-bounded MCP tools, resources, and prompts | [`docs/mcp.md`](docs/mcp.md) |

Cross-runtime frontmatter compilation is documented in
[`docs/runtimes.md`](docs/runtimes.md); fixture evals and dated baselines in
[`docs/evals.md`](docs/evals.md); repository-as-source ingestion in
[`docs/repo-source.md`](docs/repo-source.md).

`pack` writes `<skill>.zip` next to the package by default (`--zip` overrides
the path); its `--packer` label is self-asserted, and `--verify-signature`
checks the detached `skillarum.sig` signature stored inside the archive.
`diff` compares two rendered packages at hash and section level. `serve`
exposes a rendered-skills directory over read-only HTTP with `--skills-dir`,
`--host` (default `127.0.0.1`), and `--port` (default `8765`; `0` selects an
ephemeral port). `snapshot-site` additionally accepts `--archive`,
`--archive-only`, `--max-pages`, and `--max-requests`; see
[the source refresh runbook](docs/source-refresh.md).

Extension recipes — new generation backends, fetchers, policy packs, MCP
tools, figures, and manuscript tokens — are in
[`docs/extending.md`](docs/extending.md).

## Development setup

```bash
uv sync --extra dev --extra research
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
```

The research extra supplies the plotting dependencies used by the figure tests.

## Generation backends

The deterministic backend is offline and source-extractive. The optional
OpenAI backend requires `uv sync --extra llm` and `OPENAI_API_KEY`:

```bash
uv run --extra llm python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend openai \
  --model gpt-4o-mini
```

The command backend sends a JSON `PreparedCorpus` payload to an executable on
stdin and expects a JSON object containing `name`, `description`, and `body` on
stdout:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend command \
  --generator-command python path/to/generator.py
```

Ollama is a first-class local backend. It calls Ollama's structured-output chat
API and defaults to `http://127.0.0.1:11434` and the `llama3.2` model:

```bash
ollama pull llama3.2
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend ollama \
  --ollama-model llama3.2
```

The client requests an 8,192-token Ollama context by default and bounds the
source prompt to a conservative character budget before sending it. If a
bundle is larger, the prompt is explicitly marked and truncation is recorded
in manifest metadata; use `--ollama-context` and
`--ollama-max-prompt-chars` to tune this for a larger local model.

For a resilient provider chain, use `auto`: it tries OpenAI when
`OPENAI_API_KEY` is present, then Ollama, then the deterministic generator.
Alternatively, choose an explicit fallback such as
`--backend openai --fallback-backend ollama`. Fallback use and the triggering
error are retained in a typed generation trace in the skill and run manifests;
cache identities include the whole provider chain. A provider is retried twice
by default for transport failures, timeouts, HTTP 408/429/5xx, and transient
Ollama daemon failures. Malformed JSON, invalid output schema, unsafe output,
and other deterministic validation failures are not retried and can proceed to
the configured fallback.

The backend and all provider settings can be declared under a profile's
`generation` mapping. CLI arguments override profile defaults only when they
are supplied. `auto` is opt-in; the profile and CLI default remain
`deterministic`. Credentials are environment-only (`OPENAI_API_KEY`,
`OLLAMA_HOST`, and `OLLAMA_MODEL`) and are excluded from cache and manifests.

The requested profile target name is authoritative for rendered paths across
all backends. If an LLM suggests another name, it is retained only as metadata
and cannot redirect the artifact to an unexpected skill directory.

Generated Markdown is validated before the command succeeds:

```bash
uv run python -m skillarum validate output/skills/Math4Wisdom/Three-Minds/SKILL.md
```

Generated skills are organized by source area. The two canonical areas are
`Math4Wisdom/` and `Active-Inference-Institute/`; each contains one or more
portable skill packages. The discovery index records the area explicitly, so
identical skill names can safely coexist across source sites. Generated skills
use a common structure: semantic knowledge, procedural guidance, verification,
and renderer-added provenance. This keeps the output portable across Codex,
Claude Code, Hermes, and similar harnesses.

## Idempotency and recovery

The persisted contract is pipeline `0.8`, cache version `7`, and skill manifest
schema `2`. Acquisition envelopes validate profile and target fingerprints,
payload hashes, and schema versions. Draft envelopes additionally validate the
prepared-corpus fingerprint, generator fingerprint, generation configuration,
and the typed attempt trace. A version change intentionally makes older caches
stale instead of silently reusing them.

Each target is protected by an interprocess lock under
`output/.cache/locks/`. Package publication stages `SKILL.md` and
`manifest.json` together, validates the staged package, then replaces the
directory through atomic renames with a recoverable backup and a brief absence
window. The index is rebuilt only from complete hash-valid packages.
Runs persist `planned`, `acquiring`, `preparing`, `generating`, `validating`,
`rendered`, or `failed` state in `output/runs/<run-id>/state.json`; failed runs
also retain `failure.json` for safe diagnosis and resumption.

The crawler separates accepted-page limits from request limits. `max_pages`
counts accepted, de-duplicated pages; `max_requests` counts every page,
redirect, robots, and retry attempt. Responses are read in bounded streaming
chunks, robots and normal requests share the rate limiter, and transient HTTP
responses honor bounded `Retry-After` delays. Every acquisition event records
whether it represents a real request attempt, so research counters cannot
mistake selection rejections, duplicate notices, or redirect metadata for
network requests. Hostnames are resolved immediately before public acquisition
and private/reserved answers are rejected. The fetcher protocol is the v1
boundary for a future browser-backed implementation; the shipped fetcher is
static HTTP only.

Run and validation summaries can be consumed without parsing human output:

~~~bash
uv run python -m skillarum run --profile data/sources/math4wisdom.yaml --json
uv run python -m skillarum validate --json output/skills/Math4Wisdom/Three-Minds/SKILL.md
~~~

## Safety and provenance

Only HTTP(S) pages on the configured origin are followed by default. The
crawler respects `robots.txt`, manually validates each redirect before
following it, limits page count, depth, redirects, response size, and request
rate, and records redirects, canonical URLs, hashes, warnings, and retrieval
timestamps. Source text is delimited as untrusted data for LLM generation;
generated code is never executed.

Ollama connection settings can also be supplied with `OLLAMA_HOST` and
`OLLAMA_MODEL`. The live Ollama test is opt-in with
`SKILLARUM_RUN_OLLAMA=1`; the default suite uses a real local
Ollama-compatible HTTP server and does not require a daemon or downloaded
model.

See [`docs/architecture.md`](docs/architecture.md) for data contracts and
stage boundaries, and [`docs/v1-boundary.md`](docs/v1-boundary.md) for
deliberate non-goals.

## Scholarly evaluation and publication

From existing run snapshots, build the research inputs in one offline command:

```bash
uv run --extra research python -m skillarum research build --output-dir output --json
```

The build writes an ordered receipt and leaves PDF/HTML rendering pending.
See [the release checklist](docs/release-checklist.md) for the full sequence.


Skillarum also emits an evidence-gated research package. It aggregates
completed run manifests without changing the crawler or generator contract:

```bash
uv run python -m skillarum evaluate --output-dir output --json
uv run python -m skillarum figures \
  --evaluation output/reports/evaluation-summary.json --json
uv run python -m skillarum research validate --manuscript-dir docs/manuscript --json
uv run python -m skillarum research manuscript \
  --evaluation output/reports/evaluation-summary.json \
  --source-dir docs/manuscript --render --json
uv run python -m skillarum research publication --output-dir output --json
```

Both manuscript directory flags are optional; their default is `docs/manuscript`.
The `--render` flag writes hydrated Markdown, not PDF/HTML.

Evaluation observations report page/request counts, redirects, truncation,
cache hits, provider attempts, fallback behavior, generation timing, package
integrity, and provenance completeness. Small samples receive descriptive
statistics and exact binomial intervals only; the system does not invent
significance claims. Human ratings use a 0–4 rubric for semantic coverage,
procedural usefulness, verification, provenance, safety, and readability.
Agreement remains pending until two independent rating files contain at least
one paired case. Supply split files by repeating `--ratings`; the CLI rejects
duplicate `(case_id, rater_id)` rows:

Evidence origin is persisted per target: loopback acquisitions are `fixture`;
public evaluation with `--live --refresh` records `live`. Legacy undeclared
runs and newly reused public cache bundles remain `unknown`. Offline
aggregation preserves the recorded origin; `--live` only permits acquisition. A
schema-2 observation also checks the rendered snapshot against the run's
prepared-corpus payload page by page; a package can remain structurally valid
while its research provenance is rejected if that lineage is altered.

`rater-1.csv`/`rater-2.csv` below are illustrative filenames a human rater
fills in by hand; generate a blank starting point per rater with
`research ratings-template --output data/evaluation/rater-1.csv --case <case-id>`
(repeat with a different `--output` per rater):

```bash
uv run python -m skillarum evaluate --output-dir output \
  --ratings data/evaluation/rater-1.csv \
  --ratings data/evaluation/rater-2.csv --json
```

Validate an adjudication against the exact rating files used for it with
`research validate --ratings <file> --ratings <file> --adjudication <json>`.

The manuscript sources live under [`docs/manuscript/`](docs/manuscript/), citations and
claims under [`data/`](data/), and reproducible SVG/PNG figures under
`output/figures/`. Generated skills intentionally remain source-bounded;
external scholarship belongs in the manuscript and bibliography rather than in
portable skill packages. PDF/HTML rendering of the manuscript is performed
by an external parent-template engine that is intentionally not copied into
this repository.

## Author and publication metadata

The manuscript author is Daniel Ari Friedman, Active Inference Institute,
ORCID [`0000-0001-6232-9096`](https://orcid.org/0000-0001-6232-9096). Release
0.2.0 (release date 2026-09-08) is identified by the version DOI
[`10.5281/zenodo.22663907`](https://doi.org/10.5281/zenodo.22663907), the
repository <https://github.com/docxology/Skillarum>, and the release
<https://github.com/docxology/Skillarum/releases/tag/v0.2.0>. The
machine-readable citation record is [`CITATION.cff`](CITATION.cff), the full
identifier inventory is in [`docs/publication.md`](docs/publication.md), and
the cover asset is documented with its hash, dimensions, caption, alt text,
and limitations in [`data/cover.yaml`](data/cover.yaml).
`research publication` writes `output/reports/publication-manifest.json`, an
explicit hash inventory of publishable skills, research files, figures, PDF,
and HTML. The current report is selected through
`output/reports/evaluation-manifest.json`; stale evaluation snapshots and
local `AGENTS.md`/`README.md` guidance are excluded. Private caches/runs,
symlinks, and credential markers are rejected and validated.

For release validation, materialize project metadata and require parent-rendered
outputs:

~~~bash
uv run python -m skillarum research publication \
  --output-dir output --project-root . --require-rendered --json
~~~

This hashes the cover, citation record, claims ledger, citation ledger, cover
metadata, and manuscript configuration alongside the generated publication
surface. Command-provider diagnostics contain only redacted command arguments;
API keys and authorization values never enter manifests or cache identities.

The report ID is deterministic for the observation and rating payload. The
envelope's `generated_at` timestamp is intentionally operational provenance,
so repeated evaluation may produce different envelope bytes while retaining
the same report identity and observation content. Do not present the timestamp
as a reproducibility guarantee; compare the report ID, observation hashes, and
publication manifest hashes instead.

Generated packages preserve human-facing paths such as
`output/skills/Math4Wisdom/Three-Minds/` and
`output/skills/Active-Inference-Institute/Institute-Overview/`, while the
frontmatter `name` is the lowercase portable slug required by Codex (for
example `three-minds`). The manifest retains both `requested_skill_name` and
`portable_name`, so target authority is not lost for portability. Verify either
canonical example with Codex’s validator:

```bash
uv run python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  output/skills/Math4Wisdom/Three-Minds
uv run python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  output/skills/Active-Inference-Institute/Institute-Overview
```

Install and verify a generated package with the supported CLI:

```bash
uv run python -m skillarum install output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex
uv run python -m skillarum drift output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
```

The installer stages the full package and its receipt before replacement;
`drift` checks all companion files as well as `SKILL.md`.

For operational details on cache invalidation, provider budgeting, local
Ollama checks, and publication gates, see
[`docs/operations.md`](docs/operations.md).

For an empty-cache refresh and a broader dated inventory of both source websites,
see [the source refresh runbook](docs/source-refresh.md). The full HTML inventory
is retained separately from the seven bounded skill bundles. Harness installation
uses each skill's portable frontmatter name, so a refresh replaces the existing
slug directory rather than creating a differently named copy.

Manuscript results, reporting settings, profile tables, and figure captions are
source-bound; see [the binding contract](docs/manuscript-bindings.md).

Skillarum itself is available as an authored [operator skill](skills/skillarum/SKILL.md)
and a [local MCP server](docs/mcp.md). The operator skill contains software
workflow guidance; the generated website skills retain their separate,
source-bounded provenance contract.

## Citing Skillarum

If you use Skillarum in research or practice, please cite it through
[`CITATION.cff`](CITATION.cff). Plain-text form:

> Daniel Ari Friedman (2026). *Skillarum: Conditionally Reproducible
> Website-to-Agent-Skill Compilation*, version 0.2.0.
> Source: <https://github.com/docxology/Skillarum>

## License

Released under the MIT License; see [`LICENSE`](LICENSE). Copyright (c) 2026
Daniel Ari Friedman, Active Inference Institute.
