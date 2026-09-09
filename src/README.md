# src/

Source root for the `skillarum` distribution. It holds no files of its own —
only the package directory.

## Contents

| Path | Purpose |
| --- | --- |
| `skillarum/` | The importable package: CLI, pipeline stages, generators, renderer, research layer |

Build metadata directories (`*.egg-info/`) may appear here after an editable
install. They are generated, git-ignored, and not documented.

## Quick start

```bash
uv pip install -e ".[dev]"
uv run python -m skillarum --help
```

`pyproject.toml` declares `[tool.setuptools.packages.find] where = ["src"]` and
`[tool.pytest.ini_options] pythonpath = ["src"]`, so both the installed package
and the test suite resolve from this directory.

## Key facts

- Layout is src-layout: nothing is importable from the project root.
- The distribution name is `skillarum`; the version is read dynamically from
  `skillarum.__version__`.
- Coverage is measured over `source = ["src"]` with `fail_under = 90`.

## More information

- [`AGENTS.md`](AGENTS.md) — packaging rules for this directory
- [`skillarum/README.md`](skillarum/README.md) — module map and quick start
- [`skillarum/AGENTS.md`](skillarum/AGENTS.md) — module responsibilities and layer contract
