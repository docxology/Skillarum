"""Edge-coverage tests for the serve discovery surface and repo-source ingestion.

Uses real directories, a real HTTP server, and real git subprocesses; no mock
frameworks.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from skillarum.repo_source import (
    extract_entrypoints,
    extract_readme_commands,
    repo_context_text,
    repo_fingerprint,
)
from skillarum.serve import build_cards, serve_skills


def _write_skill(root: Path, name: str, manifest: dict[str, object] | str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    manifest_body = json.dumps(manifest) if not isinstance(manifest, str) else manifest
    (skill_dir / "manifest.json").write_text(manifest_body, encoding="utf-8")
    return skill_dir


def test_build_cards_skips_hidden_malformed_and_incomplete(tmp_path, rendered_skill):
    root = tmp_path / "skills"
    root.mkdir()
    import shutil

    good = root / rendered_skill.parent.name
    shutil.copytree(rendered_skill.parent, good)
    _write_skill(root, ".hidden", {"skill_name": "Hidden"})
    _write_skill(root, "broken", "{not json")
    orphan = root / "orphan"
    orphan.mkdir()
    (orphan / "manifest.json").write_text("{}", encoding="utf-8")

    cards = build_cards(root)
    assert len(cards) == 1
    assert cards[0]["path"] == good.name
    assert cards[0]["effect"] in {"readonly", "mutating", "destructive"}


def test_serve_routes_cover_index_skills_and_errors(tmp_path, rendered_skill):
    root = tmp_path / "skills"
    root.mkdir()
    import shutil

    skill_dir = root / rendered_skill.parent.name
    shutil.copytree(rendered_skill.parent, skill_dir)
    (root / "index.json").write_text('{"built": true}', encoding="utf-8")

    server, base_url = serve_skills(root)
    try:
        with urllib.request.urlopen(f"{base_url}/healthz") as resp:
            assert json.loads(resp.read()) == {"status": "ok"}
        with urllib.request.urlopen(f"{base_url}/") as resp:
            payload = json.loads(resp.read())
        assert payload["ok"] and len(payload["skills"]) == 1
        with urllib.request.urlopen(f"{base_url}/index.json") as resp:
            assert json.loads(resp.read()) == {"built": True}
        with urllib.request.urlopen(
            f"{base_url}/skills/{skill_dir.name}/SKILL.md"
        ) as resp:
            assert b"# " in resp.read()
        for path in ("/skills/does-not-exist", "/nope"):
            try:
                urllib.request.urlopen(f"{base_url}{path}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
            else:  # pragma: no cover - guard
                raise AssertionError(f"expected 404 for {path}")
    finally:
        server.shutdown()
        server.server_close()


def test_serve_returns_404_when_index_missing(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    server, base_url = serve_skills(root)
    try:
        try:
            urllib.request.urlopen(f"{base_url}/index.json")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
            assert json.loads(exc.read()) == {"error": "no index built"}
        else:  # pragma: no cover - guard
            raise AssertionError("expected 404 without index.json")
    finally:
        server.shutdown()
        server.server_close()


def test_repo_fingerprint_falls_back_to_tree_hash(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "module.py").write_text("print('hi')\n", encoding="utf-8")
    tree = repo_fingerprint(plain)
    assert tree["type"] == "tree"
    assert len(tree["sha"]) == 64

    real = tmp_path / "repo"
    real.mkdir()
    (real / "module.py").write_text("print('hi')\n", encoding="utf-8")
    import subprocess

    subprocess.run(["git", "init", "-q", str(real)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(real),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
    )
    commit_sha = repo_fingerprint(real)
    assert commit_sha["type"] == "git_worktree"
    assert len(commit_sha["sha"]) == 64
    assert len(commit_sha["commit_sha"]) == 40


def test_iter_repo_files_skips_oversized_and_ignored(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "__pycache__").mkdir()
    (repo / "ignored.bin").write_bytes(b"x")
    (repo / "big.py").write_text("x" * 600_000, encoding="utf-8")
    (repo / "keep.py").write_text("ok = True\n", encoding="utf-8")
    text = repo_context_text(repo)
    assert "keep.py" in text
    assert "big.py" not in text
    assert "ignored.bin" not in text


def test_extract_entrypoints_and_readme_commands(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / "Makefile").write_text("all:\n\techo hi\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "Run it:\n\n```sh\nuv run skillarum --help\n```\n\nAlso `$ pipx install x`\n",
        encoding="utf-8",
    )
    entrypoints = extract_entrypoints(repo)
    assert set(entrypoints) == {"readme", "package_json", "makefile"}
    assert extract_readme_commands(repo) == ["uv run skillarum --help"]

    empty = tmp_path / "empty"
    empty.mkdir()
    assert extract_entrypoints(empty) == {}
    assert extract_readme_commands(empty) == []
