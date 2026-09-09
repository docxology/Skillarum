"""Structured JSON error contract: {ok, error_type, error, command}.

Covers both argparse-level usage errors (JSONArgumentParser emits the
shape when --json was on the command line) and runtime failures of
individual commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_KEYS = {"ok", "error_type", "error", "command"}


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


def assert_error_shape(stdout: str) -> dict[str, object]:
    payload = json.loads(stdout)
    assert REQUIRED_KEYS <= set(payload)
    assert payload["ok"] is False
    assert isinstance(payload["error_type"], str) and payload["error_type"]
    assert isinstance(payload["error"], str) and payload["error"]
    return payload


@pytest.fixture
def invalid_skill(tmp_path: Path) -> Path:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# no description\n", encoding="utf-8")
    return skill


def test_argparse_missing_required_argument_emits_json() -> None:
    proc = run_cli("validate", "--json")
    assert proc.returncode == 2
    payload = assert_error_shape(proc.stdout)
    assert payload["command"] == "validate"
    assert payload["error_type"] == "usage_error"


def test_argparse_unknown_command_emits_json() -> None:
    proc = run_cli("definitely-not-a-command", "--json")
    assert proc.returncode == 2
    payload = assert_error_shape(proc.stdout)
    assert payload["error_type"] == "usage_error"


def test_argparse_unknown_flag_emits_json(tmp_path: Path) -> None:
    proc = run_cli("validate", str(tmp_path), "--no-such-flag", "--json")
    assert proc.returncode == 2
    payload = assert_error_shape(proc.stdout)
    assert payload["command"] == "validate"


def test_runtime_error_json_carries_command(tmp_path: Path) -> None:
    proc = run_cli("run", "--json", "--profile", str(tmp_path / "missing.yaml"))
    assert proc.returncode == 1
    payload = assert_error_shape(proc.stdout)
    assert payload["command"] == "run"
    assert payload["error_type"] == "FileNotFoundError"


def test_pack_error_json_carries_command(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: x\n---\n\n# no description\n", encoding="utf-8")
    proc = run_cli("pack", str(skill), "--json")
    assert proc.returncode == 1
    payload = assert_error_shape(proc.stdout)
    assert payload["command"] == "pack"
    assert payload["skill"] == str(skill)


def test_text_mode_errors_stay_text(tmp_path: Path) -> None:
    proc = run_cli("run", "--profile", str(tmp_path / "missing.yaml"))
    assert proc.returncode == 1
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout)
