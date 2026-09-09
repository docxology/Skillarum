# scripts/ agent guidance

## Overview

Scripts are thin entrypoints. Put reusable behavior under
[`../src/skillarum/`](../src/skillarum/) and invoke it from
`scripts/run_skillarum.py` or the package CLI. This directory exists so a
checkout can be driven without installing a console script; it is not a place
for logic.

## File organization

| File | Purpose |
| --- | --- |
| `run_skillarum.py` | Forward the package CLI exit code |
| `rescrape_sites.py` | Forward `snapshot-site`; no acquisition logic here |
| `z_generate_manuscript_variables.py` | Call the offline research build |
| `README.md` | Quick reference |
| `AGENTS.md` | This file |

`run_skillarum.py` in full is a docstring, a `sys` import, an import of
`skillarum.cli.main`, and `raise SystemExit(main(sys.argv[1:]))` under a
`__main__` guard. It parses nothing and decides nothing.

## Layer contract

- ❌ No argument parsing here. Argument parsing belongs to
  [`../src/skillarum/cli.py`](../src/skillarum/cli.py).
- ❌ No network, filesystem, or provider access here.
- ❌ No exit codes invented here. Codes come from
  [`../src/skillarum/exit_codes.py`](../src/skillarum/exit_codes.py) and must
  propagate unchanged.
- ✅ A new wrapper is acceptable only when it adds no behavior a CLI subcommand
  could carry. Prefer adding a subcommand.

## Equivalent invocations

Run from the project root:

```bash
uv run python scripts/run_skillarum.py <command> [...]
uv run python -m skillarum <command> [...]
uv run skillarum <command> [...]
```

The third form requires the package to be installed; the console entrypoint is
declared in [`../pyproject.toml`](../pyproject.toml).

## Testing

There is no dedicated test module for this directory. CLI behavior is covered
by [`../tests/test_pipeline_cli.py`](../tests/test_pipeline_cli.py),
[`../tests/test_cli_edges.py`](../tests/test_cli_edges.py),
[`../tests/test_exit_codes.py`](../tests/test_exit_codes.py), and
[`../tests/test_json_errors.py`](../tests/test_json_errors.py), which drive the
package CLI directly.

## See also

- [`README.md`](README.md) — quick reference
- [`../src/skillarum/AGENTS.md`](../src/skillarum/AGENTS.md) — where behavior lives
- [`../AGENTS.md`](../AGENTS.md) — project layer contract
- [`../docs/operations.md`](../docs/operations.md) — operational runbook

`z_generate_manuscript_variables.py` is the thin parent-template pre-render hook. It calls `skillarum.publication.build_research_package` to refresh reports, figures, and variables before PDF/HTML rendering, and propagates failed gates as a nonzero process exit. It performs no acquisition.
