"""Subprocess-level exit-code contract for the Skillarum CLI.

The contract is defined in ``src/skillarum/exit_codes.py``:
0 ok, 1 validation/verification failure, 2 usage/config error,
3 environment/network failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from skillarum.exit_codes import (
    EXIT_ENVIRONMENT,
    EXIT_FAILURE,
    EXIT_OK,
    EXIT_USAGE,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "skillarum", *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        env=env,
        timeout=120,
    )


VALID_SKILL = (
    "---\nname: Test\ndescription: Test skill\n---\n\n# Test\n\n"
    "## Source boundaries\n\nFixture source.\n\n"
    "## Semantic knowledge\n\nFixture semantics.\n\n"
    "## Procedural guidance\n\nFixture procedure.\n\n"
    "## Verification\n\nFixture verification.\n"
)


@pytest.fixture
def valid_skill(tmp_path: Path) -> Path:
    skill = tmp_path / "SKILL.md"
    skill.write_text(VALID_SKILL, encoding="utf-8")
    return skill


@pytest.fixture
def invalid_skill(tmp_path: Path) -> Path:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# no description\n", encoding="utf-8")
    return skill


def test_success_commands_exit_zero(valid_skill: Path, tmp_path: Path) -> None:
    assert run_cli("validate", str(valid_skill)).returncode == EXIT_OK
    assert (
        run_cli("index", "--skills-dir", str(tmp_path / "skills")).returncode == EXIT_OK
    )
    assert run_cli("verify", str(valid_skill)).returncode == EXIT_OK
    assert (
        run_cli("cache", "inspect", "--output-dir", str(tmp_path)).returncode == EXIT_OK
    )
    assert (
        run_cli(
            "doctor", "--no-network", "--output-dir", str(tmp_path / "doctor")
        ).returncode
        == EXIT_OK
    )
    assert (
        run_cli(
            "research",
            "ratings-template",
            "--output",
            str(tmp_path / "r.csv"),
            "--case",
            "case-1",
        ).returncode
        == EXIT_OK
    )


def test_validation_failure_exits_one(
    valid_skill: Path, invalid_skill: Path, tmp_path: Path
) -> None:
    assert run_cli("validate", str(invalid_skill)).returncode == EXIT_FAILURE
    assert run_cli("verify", str(invalid_skill)).returncode == EXIT_FAILURE
    assert (
        run_cli("pack", str(invalid_skill), "--zip", str(tmp_path / "x.zip")).returncode
        == EXIT_FAILURE
    )
    # missing input artifact is a validation failure of the requested inputs
    assert (
        run_cli("validate", str(tmp_path / "missing-SKILL.md")).returncode
        == EXIT_FAILURE
    )
    assert (
        run_cli("run", "--profile", str(tmp_path / "missing.yaml")).returncode
        == EXIT_FAILURE
    )
    # drift against an empty fake home reports drifted -> failure code
    assert (
        run_cli(
            "drift",
            str(valid_skill),
            "--harness",
            "claude",
            "--home",
            str(tmp_path / "empty-home"),
        ).returncode
        == EXIT_FAILURE
    )


def test_usage_error_exits_two(tmp_path: Path) -> None:
    assert run_cli().returncode == EXIT_USAGE
    assert run_cli("no-such-command").returncode == EXIT_USAGE
    assert run_cli("validate").returncode == EXIT_USAGE  # missing required paths
    assert run_cli("validate", str(tmp_path), "--no-such-flag").returncode == EXIT_USAGE
    assert run_cli("run").returncode == EXIT_USAGE  # missing required --profile


def test_environment_failure_exits_three(valid_skill: Path, tmp_path: Path) -> None:
    # unreachable endpoint is an environment/network failure, not a usage error
    result = run_cli(
        "doctor",
        "--json",
        "--output-dir",
        str(tmp_path / "doctor"),
        "--ollama-url",
        "http://127.0.0.1:1",  # nothing listens on port 1
        "--timeout",
        "1.0",
    )
    assert result.returncode == EXIT_ENVIRONMENT
    payload = json.loads(result.stdout)
    assert payload["ok"] is False


def test_exit_code_constants_are_stable() -> None:
    assert (EXIT_OK, EXIT_FAILURE, EXIT_USAGE, EXIT_ENVIRONMENT) == (0, 1, 2, 3)
