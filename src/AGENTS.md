# src/ agent guidance

## Overview

`src/` is the packaging boundary, not a code location. It contains exactly one
tracked subdirectory, [`skillarum/`](skillarum/), which is the entire
implementation. Nothing else belongs here.

## Directory structure

| Path | Tracked | Purpose |
| --- | --- | --- |
| `skillarum/` | yes | The package — see [`skillarum/AGENTS.md`](skillarum/AGENTS.md) |
| `*.egg-info/` | no | setuptools build metadata from an editable install; git-ignored |

An `.egg-info` directory left behind by a previous distribution name is inert
build residue. It is not deleted by this documentation pass and should not be
imported, read, or documented.

## Why src-layout

`pyproject.toml` sets:

```toml
[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

The consequence is that tests exercise the same import path an installed user
gets. A module that is importable only because the project root happens to be
on `sys.path` will fail for a real install, and the layout makes that failure
show up immediately.

## Rules

- ✅ Add new modules under `skillarum/`, never directly in `src/`.
- ✅ Keep the package importable without optional extras installed. The
  `openai` and `matplotlib` dependencies are optional at run time and must be
  imported lazily.
- ❌ Do not add a second top-level package here without changing
  `[tool.setuptools.packages.find]` and the coverage configuration.
- ❌ Do not commit `*.egg-info/` content.

## Build and install

```bash
uv sync --extra dev
uv pip install -e ".[dev,llm,research]"
uv run python -c "import skillarum; print(skillarum.__version__)"
```

## Testing

```bash
uv run pytest tests/ --cov=src --cov-fail-under=90
```

Coverage omits `*/__init__.py` and `*/__main__.py` and is measured with branch
coverage on.

## See also

- [`README.md`](README.md) — quick reference
- [`skillarum/AGENTS.md`](skillarum/AGENTS.md) — module responsibilities
- [`../AGENTS.md`](../AGENTS.md) — project layer contract
- [`../docs/architecture.md`](../docs/architecture.md) — stage and trust boundaries
