# src/skillarum/ agent guidance

## Overview

The `skillarum` package is the entire implementation of the website-to-agent-
skill pipeline. It is a flat set of Python modules, no subpackages. Each
module owns one responsibility and the boundaries between them are load-bearing
— the layer contract in the project root
[`AGENTS.md`](../../AGENTS.md) is enforced here, not merely described.

## Key concepts

**Five stages.** `acquire → prepare → process → parse → render`. Each stage
writes an inspectable artifact, so a failure is diagnosable without rerunning
the previous stage.

**Two products, one boundary.** Generated `SKILL.md` packages are
source-bounded and untrusted. Citations, comparative interpretation, figures,
and manuscript claims belong only to the research layer. No module may move
content across that boundary.

**Deterministic core.** `models.py`, `config.py`, `prepare.py`, and `urls.py`
are contracts and pure transformations, with one deliberate exception:
`urls.is_public_http_url(..., resolve_dns=True)` performs a live
`socket.getaddrinfo` lookup as an SSRF safety check. `crawler.py` calls it at
five sites, four of which pass `resolve_dns=True` and resolve DNS. It stays in
`urls.py` as a reusable URL-classification predicate, not because it is
side-effect-free.

## File organization

### Entry points

| Module | Responsibility |
| --- | --- |
| `__init__.py` | `__version__ = "0.2.0"`; re-exports the model and research dataclasses |
| `__main__.py` | `python -m skillarum` → `cli.main()` |
| `cli.py` | All argument parsing, command dispatch, JSON output, exit codes |

### Contracts and helpers

| Module | Responsibility |
| --- | --- |
| `models.py` | Typed contracts: `SourceProfile`, `CrawlConfig`, `ExtractionConfig`, `GenerationConfig`, `TargetSpec`, `RetryConfig`, `PageRecord`, `BundleRecord`, `PreparedPage`, `PreparedCorpus`, `SkillDraft`, `GenerationAttempt`, `GenerationTrace` |
| `config.py` | `load_profile()` / `profile_from_mapping()` — YAML → validated `SourceProfile` |
| `urls.py` | URL normalization, target matching, and the public-host SSRF predicate |
| `utils.py` | Small pure helpers (hashing, canonical JSON, slugs) |
| `exit_codes.py` | `EXIT_OK=0`, `EXIT_FAILURE=1`, `EXIT_USAGE=2`, `EXIT_ENVIRONMENT=3` |

### Pipeline stages

| Module | Responsibility |
| --- | --- |
| `crawler.py` | The only module that fetches pages over HTTP: robots handling, redirect validation, rate limiting, bounded streaming reads, HTML extraction |
| `prepare.py` | Deterministic corpus preparation before generator execution |
| `generators.py` | Deterministic, OpenAI, Ollama, and external-command backends behind one `generate(corpus) -> SkillDraft` contract, with a shared retry/trace harness |
| `render.py` | Portable `SKILL.md` rendering, transactional publication, structural validation |
| `pipeline.py` | Filesystem stage orchestration, run state, locking, cache identity |

`site_snapshot.py` extends the crawler for fresh, bounded public HTML inventories.
It retains raw response receipts, verifies page and bundle hashes, and creates
local archives with separately reported coverage limits. Network operations
still use `crawler.py`. Archive summaries are checked against their archived
receipts before entering a manuscript.

### Alternative source

| Module | Responsibility |
| --- | --- |
| `repo_source.py` | A local git repository as a second source type: entrypoint detection, README command extraction, commit-SHA fingerprint. No cloning, no network. Library surface only today — no CLI flag wires it into `run` yet |

### Package lifecycle

| Module | Responsibility |
| --- | --- |
| `install.py` | Install into a harness skills root and record a sidecar manifest; `harness_roots()` maps `codex`, `claude`, `agents` to `.<name>/skills`, joined with the configured home (`~/.<name>/skills` by default) |
| `packdiff.py` | Hash-level and section-level comparison of two rendered packages |
| `signature.py` | Detached SHA-256 pack signatures stored inside the archive as `skillarum.sig` |
| `runtimes.py` | Per-target frontmatter allowlists and length limits for the `agentskills`, `claude`, and `codex` runtimes; library utility with no internal caller yet |
| `quarantine.py` | A refreshed draft that differs from the cached canonical is quarantined until a second clean regeneration confirms it |

### Safety

| Module | Responsibility |
| --- | --- |
| `policies.py` | The `security` policy pack: seven severity-ranked rules — `curl_pipe_shell`, `wget_pipe_shell`, `sudo_usage`, `rm_rf`, `hardcoded_secret`, `absolute_home_path`, `env_var_credentials` |
| `redaction.py` | Two-pass defense: scrub credential-shaped tokens before write, then assert non-leakage in every output payload |

### Surfaces

| Module | Responsibility |
| --- | --- |
| `mcp_server.py` | Root-confined MCP stdio tools for discovery, gated index reconstruction, package validation/inspection, and evaluation reports; resources and a review prompt |
| `serve.py` | Read-only HTTP discovery: `/index.json`, `/healthz`, `/skills/…`. Invocation is deliberately out of scope |

### Research layer

`publication.py` owns `build_research_package()`, the offline build and ordered
receipt. It calls the existing evaluation, figure, and manuscript owners.


| Module | Responsibility |
| --- | --- |
| `research.py` | Turns persisted run manifests into auditable observations; citation/claim ledgers, ratings, adjudication, publication manifest; compatibility exports for statistics and manuscript functions |
| `statistics.py` | Validated reporting policy, exact binomial intervals, bootstrap summaries, ordinal diagnostics and weighted kappa |
| `manuscript.py` | Source-derived variables, captions and tables; numeric-prose guard and independent binding reconstruction |
| `figures.py` | Deterministic SVG figures (canonical) with PNG companions and an auditable figure registry |
| `evals.py` | Fixture evaluation with release-blocking numeric gates and dated baselines |

`evals.py` is imported by the test suite rather than by other package modules;
it is a release gate, not a pipeline stage.

## Layer contract

- ✅ `crawler.py` is the only module that fetches pages over HTTP. Outbound
  provider HTTP is confined to `generators.py`; `cli.py` issues a live Ollama
  `/api/tags` request for `doctor` unless `--no-network`; `serve.py` opens a
  local listening socket; nothing else dials out.
- ✅ `research.py` stays independent of provider and crawler internals. It
  reads persisted manifests, never live state.
- ✅ Optional dependencies (`openai`, `matplotlib`) are imported lazily. The
  deterministic backend must work with no credentials, no daemon, and no
  downloaded model.
- ✅ Command handlers return a code from `exit_codes.py`.
- ❌ Never execute generated content. Generated code is data.
- ❌ Never let a credential reach a cache identity, a manifest, or a diagnostic
  message. Command-provider diagnostics carry redacted arguments only.
- ❌ Never let the renderer redirect an artifact to a name an LLM suggested;
  the profile target name is authoritative for the path.

## Usage examples

```python
from skillarum.config import load_profile
from skillarum.policies import POLICY_PACKS

profile = load_profile("data/sources/active_inference_institute.yaml")
print(profile.area)                       # Active-Inference-Institute
print(sorted(POLICY_PACKS))               # ['security']
```

```python
from skillarum.install import harness_roots

print(harness_roots())   # {'codex': '.codex/skills', 'claude': '.claude/skills', 'agents': '.agents/skills'}
```

## Configuration

Credentials are environment-only and excluded from caches and manifests:

| Variable | Used by |
| --- | --- |
| `OPENAI_API_KEY` | `generators.py` OpenAI backend |
| `OLLAMA_HOST` | `generators.py` Ollama backend |
| `OLLAMA_MODEL` | `generators.py` Ollama backend |

Test-only opt-in gates: `SKILLARUM_RUN_OPENAI`, `SKILLARUM_RUN_OLLAMA`,
`SKILLARUM_OPENAI_MODEL`, `SKILLARUM_OLLAMA_MODEL`.

## Testing

```bash
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
uv run ruff check src tests
uv run ruff format --check src tests
```

Tests use real local HTTP servers and real subprocesses, never mock frameworks.
See [`../../tests/AGENTS.md`](../../tests/AGENTS.md).

## Persisted contract versions

Pipeline `0.8`, cache version `7`, skill manifest schema `2`. A version bump
intentionally makes older caches stale rather than silently reusing them.

## See also

- [`README.md`](README.md) — module map and quick start
- [`../AGENTS.md`](../AGENTS.md) — packaging boundary
- [`../../docs/architecture.md`](../../docs/architecture.md) — stage and trust boundaries
- [`../../docs/policies.md`](../../docs/policies.md) — policy packs and verify exit codes
- [`../../docs/install-drift.md`](../../docs/install-drift.md) — install and drift
- [`../../docs/runtimes.md`](../../docs/runtimes.md) — cross-runtime compilation
- [`../../docs/mcp.md`](../../docs/mcp.md) — MCP stdio server
- [`../../docs/repo-source.md`](../../docs/repo-source.md) — repository ingestion
- [`../../docs/evals.md`](../../docs/evals.md) — fixture gates and baselines
- [`../../docs/v1-boundary.md`](../../docs/v1-boundary.md) — deliberate non-goals

`statistics.py` owns numerical summaries, interval routines, ordinal diagnostics,
and the validated default statistical policy. `manuscript.py` binds prose to
reports, contracts, profiles, and captions, and reconstructs expected outputs
to detect forged or stale variables. Keep their dependency boundary explicit:
manuscript generation consumes research records; it never acquires pages.
