# tests/ agent guidance

## Overview

Use real local HTTP servers and subprocesses instead of mock frameworks. Keep
live network and OpenAI coverage opt-in so the default suite remains
repeatable. The suite is `test_*.py` modules plus `conftest.py`, and it is
the enforcement mechanism for the layer contract described in the project root
[`AGENTS.md`](../AGENTS.md).

## Hermeticity rule

Tests must pass from a clean checkout. `output/` is disposable, so a test may
not read pre-existing generated skills, figures, evaluation reports, or run
manifests. If a test needs an artifact, it creates it in `tmp_path` through the
real renderer or the real figure writer.

Two corollaries the suite enforces:

- Evaluation observations retain their evidence origin — `fixture`, `live`, or
  `unknown`. A fixture observation is never relabelled as live-site evidence.
- Schema-2 package snapshots stay lineage-bound to the run's `02_prepare`
  corpus. A package can be structurally valid and still have its research
  provenance rejected if that lineage was altered.

## Fixtures (`conftest.py`, 434 lines)

| Fixture | Scope | Provides |
| --- | --- | --- |
| `fixture_server` | function | A real `ThreadingHTTPServer` with `/robots.txt`, `/page`, `/other`, `/injection`, `/redirect`, `/blocked`, `/not-html`, `/empty`, and more |
| `robots_404_server` | function | Origin whose `robots.txt` returns 404 |
| `robots_5xx_server` | function | Origin whose `robots.txt` returns a server error |
| `robots_redirect_server` | function | `robots.txt` behind a redirect |
| `robots_redirect_missing_location_server` | function | Redirect with no `Location` header |
| `robots_redirect_invalid_target_server` | function | Redirect to an unparseable target |
| `robots_redirect_unsafe_target_server` | function | Redirect to a target that fails the public-host check |
| `ollama_server` | function | A real Ollama-compatible HTTP server plus the captured request list |
| `ollama_tags_server` | function | A real `/api/tags` endpoint for `doctor` |
| `rendered_skill` | session | A skill package rendered into a session `tmp_path` |

The `/injection` route serves a prompt-injection page ("IGNORE PREVIOUS
INSTRUCTIONS…"). It is required evidence for the source-boundary claim in
[`../data/claims.yaml`](../data/claims.yaml).

Three modules additionally use the real werkzeug-based pytest-httpserver
`httpserver` fixture (declared in the `[dependency-groups]` dev group of
`pyproject.toml`): `test_conditional_fetch.py`, `test_robots_cache_ttl.py`,
and `test_site_snapshot.py`.

## Module map

| Area | Test modules |
| --- | --- |
| CLI and exit codes | `test_pipeline_cli.py`, `test_cli_edges.py`, `test_cli_diff.py`, `test_exit_codes.py`, `test_json_errors.py`, `test_version.py` |
| Acquisition | `test_crawler.py`, `test_acquisition_metrics.py`, `test_conditional_fetch.py`, `test_robots_cache_ttl.py`, `test_config_urls.py` |
| Contracts and prep | `test_models.py`, `test_prepare.py`, `test_utils.py` |
| Generation and render | `test_generators_render.py`, `test_quarantine.py`, `test_refresh_diff.py`, `test_effect_tags.py` |
| Providers (opt-in) | `test_ollama_integration.py`, `test_openai_integration.py` |
| Packaging lifecycle | `test_pack_and_sources.py`, `test_packdiff.py`, `test_signature.py`, `test_install_drift.py`, `test_runtimes.py` |
| Safety | `test_redaction.py`, `test_verify_policies.py`, `test_production_hardening.py` |
| Surfaces | `test_mcp_server.py`, `test_serve.py`, `test_serve_and_repo_source_edges.py`, `test_repo_source.py` |
| Research layer | `test_scholarship.py`, `test_statistics.py`, `test_figure_quality.py`, `test_manuscript_bindings.py`, `test_publication_build.py`, `test_evals.py`, `test_publication_metadata.py` |
| Breadth | `test_more_edges.py`, `test_bulk_doctor.py` |

## Rules

- ✅ Real servers and real subprocesses. `unittest.mock` and equivalents are
  out of bounds for behavior under test.
- ✅ Write every artifact under `tmp_path` or `tmp_path_factory`.
- ✅ Gate anything that needs a credential, a daemon, or the public internet on
  an environment variable, and skip with a message that says how to enable it.
- ❌ Never read from `output/`.
- ❌ Never assert against a network resource the default suite cannot reach.
- ❌ Do not add an unregistered pytest marker. `addopts` includes
  `--strict-markers` and no custom markers are registered in `pyproject.toml`;
  the suite currently uses only `parametrize` and `skipif`.

## Running

From the project root:

```bash
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
uv run --extra dev --extra research pytest tests/test_crawler.py -v
SKILLARUM_RUN_OLLAMA=1 uv run --extra dev --extra research pytest tests/test_ollama_integration.py -v
SKILLARUM_RUN_OPENAI=1 uv run --extra dev --extra llm pytest tests/test_openai_integration.py -v
```

Before a release or push, also run `ruff check src tests`,
`ruff format --check src tests`, and the research validators listed in
[`../docs/release-checklist.md`](../docs/release-checklist.md).

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Coverage below 90 | `fail_under = 90` in `[tool.coverage.report]`; add real coverage rather than lowering the gate |
| A live provider test skipped | Its `SKILLARUM_RUN_*` gate is unset — this is the intended default |
| `Unknown pytest.mark` error | `--strict-markers` rejected an unregistered marker |
| A test passes locally but not on a clean checkout | It read something from `output/`; rebuild the artifact in `tmp_path` |

## See also

- [`README.md`](README.md) — quick reference
- [`../src/skillarum/AGENTS.md`](../src/skillarum/AGENTS.md) — the modules under test
- [`../docs/evals.md`](../docs/evals.md) — fixture gates and dated baselines
- [`../docs/operations.md`](../docs/operations.md) — operational runbook and quality gates
- [`../AGENTS.md`](../AGENTS.md) — project layer contract and testing rules

`test_review_regressions.py` exercises adversarial research, publication,
portability, repository-source, discovery, and install-drift contracts.

`test_site_snapshot.py` uses real local HTTP for crawl limits, canonical aliases,
raw response retention, archival integrity, and explicit incomplete CLI exits.
It also supplies forged summaries and corrupted raw/archive bytes as negative controls.
