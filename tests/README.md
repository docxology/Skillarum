# tests/

Pytest suite for the `skillarum` package. 43 test modules plus `conftest.py`.

## Quick start

From the project root:

```bash
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
```

Single file or single test:

```bash
uv run --extra dev --extra research pytest tests/test_crawler.py -v
uv run --extra dev --extra research pytest tests/test_crawler.py::test_name -v
```

## Key features

- **No mock frameworks.** Network coverage runs against real local servers:
  the `ThreadingHTTPServer` fixtures in `conftest.py` plus the werkzeug-based
  pytest-httpserver `httpserver` fixture in `test_conditional_fetch.py`,
  `test_robots_cache_ttl.py`, and `test_site_snapshot.py`. Subprocess coverage
  runs real subprocesses.
- **Hermetic.** A test may not read pre-existing generated skills or figures
  from `output/`. Artifacts a test needs are built in `tmp_path` through the
  real renderer or figure writer.
- **Live coverage is opt-in.** Ollama and OpenAI live tests skip unless their
  environment gate is set, so the default suite needs no daemon, model, or key.

## Environment gates

| Variable | Effect |
| --- | --- |
| `SKILLARUM_RUN_OLLAMA=1` | Enables `test_ollama_integration.py` against a running Ollama |
| `SKILLARUM_RUN_OPENAI=1` | Enables `test_openai_integration.py` (needs the `llm` extra and `OPENAI_API_KEY`) |
| `SKILLARUM_OLLAMA_MODEL` | Overrides the model used by the live Ollama test |
| `SKILLARUM_OPENAI_MODEL` | Overrides the model used by the live OpenAI test |

## Common commands

```bash
# Default suite with the coverage gate
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90

# Opt into live Ollama coverage
SKILLARUM_RUN_OLLAMA=1 uv run --extra dev --extra research pytest tests/test_ollama_integration.py -v

# Lint and format checks that run alongside the suite
uv run ruff check src tests
uv run ruff format --check src tests
```

## Configuration

`pyproject.toml` sets `pythonpath = ["src"]`, `testpaths = ["tests"]`, and
`addopts = "-v --tb=short --strict-markers"`. Coverage is branch coverage over
`src`, omitting `__init__.py` and `__main__.py`, with `fail_under = 90`.

## More information

See [AGENTS.md](AGENTS.md) for the fixture inventory, the no-mocks rule, and
the module-to-test map.

`test_review_regressions.py` exercises adversarial research, publication,
portability, repository-source, discovery, and install-drift contracts.

`test_site_snapshot.py` uses real local HTTP for crawl limits, canonical aliases,
raw response retention, archival integrity, and explicit incomplete CLI exits.
It also supplies forged summaries and corrupted raw/archive bytes as negative controls.

`test_statistics.py` checks interval endpoints against independent numerical
oracles and tests missingness and rating-report integrity. Figure source and
point-data binding controls live in `test_figure_quality.py`.
`test_manuscript_bindings.py` reconstructs hydrated text and rejects forged or
stale evidence. `test_publication_build.py` exercises the ordered build using
real acquired fixture data, including failures after completed steps.
`test_mcp_server.py` runs the stdio server as a real subprocess and checks
protocol envelopes, root confinement, current-package discovery, and write gates.

Coverage includes Python subprocesses through Coverage.py's `subprocess` patch.
This is required for the real MCP and CLI paths with pytest-cov's current
integration; see [the upstream migration guidance](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html).
The floor still applies to the same source files and branches. Run with the
locked dev dependencies; a parent-only measurement omits code actually
executed by these subprocess tests.
