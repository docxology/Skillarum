# scripts/

Thin entrypoints. All behavior lives in
[`../src/skillarum/`](../src/skillarum/).

## Contents

| File | Purpose |
| --- | --- |
| `run_skillarum.py` | Forward arguments to the package CLI |
| `rescrape_sites.py` | Forward arguments to `snapshot-site` |
| `z_generate_manuscript_variables.py` | Offline research build before parent rendering |

## Quick start

From the project root, these three forms are equivalent:

```bash
uv run python scripts/run_skillarum.py --help
uv run python -m skillarum --help
uv run skillarum --help
```

The `skillarum` console entrypoint is declared in
[`../pyproject.toml`](../pyproject.toml) as `skillarum = "skillarum.cli:main"`.

## Common commands

```bash
uv run python scripts/run_skillarum.py run \
  --profile data/sources/math4wisdom.yaml --backend deterministic

uv run python scripts/run_skillarum.py doctor \
  --profile data/sources/math4wisdom.yaml --no-network --json

uv run python scripts/run_skillarum.py index --skills-dir output/skills
```

Exit codes are the stable contract defined in
[`../src/skillarum/exit_codes.py`](../src/skillarum/exit_codes.py).

## More information

See [AGENTS.md](AGENTS.md) for the rule that keeps this directory thin, and the
root [`../README.md`](../README.md) for the full command reference.

`z_generate_manuscript_variables.py` is the thin parent-template pre-render hook. It calls `skillarum.publication.build_research_package` to refresh reports, figures, and variables before PDF/HTML rendering, and propagates failed gates as a nonzero process exit. It performs no acquisition.
