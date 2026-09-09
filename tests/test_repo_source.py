"""Tests for repository-as-source ingestion (real local git repo fixture)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skillarum.repo_source import (
    extract_entrypoints,
    extract_readme_commands,
    repo_context_text,
    repo_fingerprint,
)


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Sample\n\nInstall:\n\n```sh\nuv sync\n```\n\nRun tests:\n\n$ uv run pytest -q\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'sample'\n", encoding="utf-8"
    )
    (repo / "pkg.py").write_text("def main() -> None:\n    pass\n", encoding="utf-8")
    (repo / ".venv" / "junk.py").parent.mkdir()
    (repo / ".venv" / "junk.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q"], cwd=str(repo), capture_output=True, timeout=30
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"],
        cwd=str(repo),
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
        cwd=str(repo),
        capture_output=True,
        timeout=30,
    )
    return repo


def test_fingerprint_is_commit_sha(sample_repo):
    fp = repo_fingerprint(sample_repo)
    assert fp["type"] == "git_commit"
    assert len(fp["sha"]) == 40


def test_fingerprint_distinguishes_commits(sample_repo):
    first = repo_fingerprint(sample_repo)["sha"]
    (sample_repo / "pkg.py").write_text(
        "def main() -> None:\n    x = 2\n", encoding="utf-8"
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-aqm", "v2"],
        cwd=str(sample_repo),
        capture_output=True,
        timeout=30,
    )
    second = repo_fingerprint(sample_repo)["sha"]
    assert first != second


def test_entrypoints_detected(sample_repo):
    markers = extract_entrypoints(sample_repo)
    assert "readme" in markers
    assert "pyproject" in markers
    assert "package_json" not in markers


def test_readme_commands_extracted(sample_repo):
    commands = extract_readme_commands(sample_repo)
    assert "uv sync" in commands
    assert "uv run pytest -q" in commands


def test_venv_files_excluded_from_context(sample_repo):
    context = repo_context_text(sample_repo)
    assert "junk.py" not in context
    assert "pkg.py" in context
    assert "repository_entrypoints" in context


def test_fingerprint_fallback_for_non_git_dir(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.md").write_text("x", encoding="utf-8")
    fp = repo_fingerprint(plain)
    assert fp["type"] == "tree"
    assert len(fp["sha"]) == 64
