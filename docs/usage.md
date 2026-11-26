# CLI and workflow reference

Run these commands from the repository root. See the [documentation index](README.md) for setup and the [fixture render guide](rendering.md) for a local publication check.

## Command reference

| Command | Purpose | Details |
| --- | --- | --- |
| `run` | Crawl targets and render skills | (this README) |
| `validate` | Validate one or more `SKILL.md` files | (this README) |
| `verify` | Round-trip a rendered skill through all validators; `--policy security` applies the security policy pack | [`docs/policies.md`](policies.md) |
| `install` | Install a validated package into a harness skills root | [`docs/install-drift.md`](install-drift.md) |
| `drift` | Read-only installed-vs-canonical drift report | [`docs/install-drift.md`](install-drift.md) |
| `pack` | Package a validated skill directory as a zip | (this README) |
| `diff` | Compare two rendered packages at hash and section level | (this README) |
| `index` | Rebuild the discovery index | (this README) |
| `serve` | Read-only HTTP discovery over rendered skills | (this README) |
| `cache inspect` | Inspect cache integrity | (this README) |
| `snapshot-site` | Capture a fresh public HTML inventory with raw receipts | [`docs/source-refresh.md`](source-refresh.md) |
| `profile-from-index` | Derive one exact-page target per link on a site's own index page | [`data/sources/AGENTS.md`](../data/sources/AGENTS.md) |
| `doctor` | Profile/output/Ollama/OpenAI health checks | (this README) |
| `evaluate` / `figures` | Research evaluation and figures | [`evaluation.md`](evaluation.md) |
| `research …` | Scholarly validation, ratings, manuscript, publication | [`evaluation.md`](evaluation.md) |
| `mcp` | Root-bounded MCP tools, resources, and prompts | [`docs/mcp.md`](mcp.md) |

Cross-runtime frontmatter compilation is documented in
[`docs/runtimes.md`](runtimes.md); fixture evals and dated baselines in
[`docs/evals.md`](evals.md); repository-as-source ingestion in
[`docs/repo-source.md`](repo-source.md).

`pack` writes `<skill>.zip` next to the package by default (`--zip` overrides
the path); its `--packer` label is self-asserted, and `--verify-signature`
checks the detached `skillarum.sig` signature stored inside the archive.
`diff` compares two rendered packages at hash and section level. `serve`
exposes a rendered-skills directory over read-only HTTP with `--skills-dir`,
`--host` (default `127.0.0.1`), and `--port` (default `8765`; `0` selects an
ephemeral port). `snapshot-site` additionally accepts `--archive`,
`--archive-only`, `--max-pages`, and `--max-requests`; see
[the source refresh runbook](source-refresh.md).

Extension recipes — new generation backends, fetchers, policy packs, MCP
tools, figures, and manuscript tokens — are in
[`docs/extending.md`](extending.md).

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

See [`docs/architecture.md`](architecture.md) for data contracts and
stage boundaries, and [`docs/v1-boundary.md`](v1-boundary.md) for
deliberate non-goals.

## Scholarly evaluation and publication

From existing run snapshots, build the research inputs in one offline command:

```bash
uv run --extra research python -m skillarum research build --output-dir output --json
```

The build writes an ordered receipt and leaves PDF/HTML rendering pending.
See [the release checklist](release-checklist.md) for the full sequence.


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

The manuscript sources live under [`docs/manuscript/`](manuscript/), citations and
claims under [`data/`](../data/), and reproducible SVG/PNG figures under
`output/figures/`. Generated skills intentionally remain source-bounded;
external scholarship belongs in the manuscript and bibliography rather than in
portable skill packages. PDF/HTML rendering of the manuscript is performed
by an external parent-template engine that is intentionally not copied into
this repository.
