"""Version reporting contract: a single constant, reflected everywhere."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import skillarum

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dunder_version_is_a_string() -> None:
    assert isinstance(skillarum.__version__, str)
    assert skillarum.__version__.count(".") >= 1


def test_pyproject_version_matches_package_constant() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # pyproject must not carry a second hand-maintained copy of the version
    assert "version" not in data["project"]
    assert "version" in data["project"]["dynamic"]
    attr = data["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert attr == "skillarum.__version__"


def test_cli_reports_version() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "skillarum", "--version"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"skillarum {skillarum.__version__}"


def test_installed_metadata_matches_constant_if_built() -> None:
    """When the package is installed in the active environment, metadata must
    be sourced from the same constant (setuptools dynamic version)."""
    try:
        from importlib.metadata import version
    except ImportError:  # pragma: no cover
        pytest.skip("importlib.metadata unavailable")
    try:
        installed = version("skillarum")
    except Exception:
        pytest.skip("skillarum not installed in this environment")
    assert installed == skillarum.__version__
