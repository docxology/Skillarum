"""Repository-as-source ingestion (second source type).

Adopted from xiaokillua/skillforge: a local git repository can seed a
prepared corpus - entrypoint detection (README, pyproject/package.json),
README command extraction, and a commit-SHA fingerprint replacing the URL
fingerprint for provenance. Cloning and network access stay out of scope
here: callers pass an already-checked-out repo path.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".mypy_cache",
}
_TEXT_SUFFIXES = {".md", ".txt", ".py", ".ts", ".js", ".toml", ".json", ".yaml", ".yml"}
_MAX_FILES = 500
_MAX_FILE_BYTES = 500_000

_README_COMMAND_RE = re.compile(
    r"^\s*(?:\$\s+|```(?:sh|bash|shell)\n)([a-zA-Z][^\n`]{2,120})$", re.M
)


def repo_fingerprint(repo_path: Path) -> dict[str, Any]:
    """Commit-SHA (or content-tree fallback) identity for a checked-out repo."""
    import hashlib
    import subprocess

    head = None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            head = proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        head = None
    # Bind the selected working-tree bytes as well as the repository commit.
    digest = hashlib.sha256()
    for file_path in _iter_repo_files(repo_path):
        relative = file_path.relative_to(repo_path).as_posix().encode()
        content = file_path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big") + relative)
        digest.update(len(content).to_bytes(8, "big") + content)
    tree_hash = digest.hexdigest()
    if head:
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=normal"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # A status that cannot run leaves the worktree state unknown, so
            # neither a clean-commit nor a dirty-worktree identity is honest;
            # degrade to the content-tree identity like a missing HEAD.
            status = None
        if status is not None and not status.stdout.strip():
            return {"type": "git_commit", "sha": head, "content_sha256": tree_hash}
        if status is not None:
            return {
                "type": "git_worktree",
                "sha": hashlib.sha256((head + tree_hash).encode()).hexdigest(),
                "commit_sha": head,
                "content_sha256": tree_hash,
            }
    return {"type": "tree", "sha": tree_hash, "content_sha256": tree_hash}


def _iter_repo_files(repo_path: Path):
    count = 0
    for directory, subdirs, files in os.walk(repo_path, followlinks=False):
        subdirs[:] = sorted(
            name
            for name in subdirs
            if name not in _IGNORED_DIRS and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(files):
            if count >= _MAX_FILES:
                return
            file_path = Path(directory) / name
            if file_path.is_symlink() or file_path.suffix not in _TEXT_SUFFIXES:
                continue
            if not file_path.is_file() or file_path.stat().st_size > _MAX_FILE_BYTES:
                continue
            count += 1
            yield file_path


def extract_entrypoints(repo_path: Path) -> dict[str, Any]:
    """Detect ecosystem entrypoints: README, pyproject, package.json, Makefile."""
    markers = {
        "readme": None,
        "pyproject": None,
        "package_json": None,
        "makefile": None,
    }
    for name in ("README.md", "readme.md", "README.rst"):
        if (repo_path / name).is_file():
            markers["readme"] = str(repo_path / name)
            break
    if (repo_path / "pyproject.toml").is_file():
        markers["pyproject"] = str(repo_path / "pyproject.toml")
    if (repo_path / "package.json").is_file():
        markers["package_json"] = str(repo_path / "package.json")
    if (repo_path / "Makefile").is_file():
        markers["makefile"] = str(repo_path / "Makefile")
    return {k: v for k, v in markers.items() if v}


def extract_readme_commands(repo_path: Path) -> list[str]:
    """Shell commands mentioned in the README (setup/usage hints for agents)."""
    for name in ("README.md", "readme.md"):
        readme = repo_path / name
        if readme.is_file():
            text = readme.read_text(encoding="utf-8", errors="surrogateescape")
            commands = _README_COMMAND_RE.findall(text)
            # dedupe preserving order
            return list(dict.fromkeys(command.strip() for command in commands))
    return []


def repo_context_text(repo_path: Path, *, max_chars_per_file: int = 20_000) -> str:
    """Prepared-corpus-style text for the generator: entrypoints + key files."""
    sections: list[str] = []
    entrypoints = extract_entrypoints(repo_path)
    sections.append(
        "<repository_entrypoints>\n"
        + json.dumps(entrypoints, indent=2, sort_keys=True)
        + "\n</repository_entrypoints>"
    )
    commands = extract_readme_commands(repo_path)
    if commands:
        sections.append(
            "<readme_commands>\n" + "\n".join(commands) + "\n</readme_commands>"
        )
    for file_path in _iter_repo_files(repo_path):
        rel = file_path.relative_to(repo_path)
        text = file_path.read_text(encoding="utf-8", errors="surrogateescape")
        sections.append(
            f'<repo_file path="{rel}">\n' + text[:max_chars_per_file] + "\n</repo_file>"
        )
    return "\n\n".join(sections)
