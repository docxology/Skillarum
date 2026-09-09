"""Tests for the read-only serve surface and index cards."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from skillarum.serve import build_cards, serve_skills


def test_build_cards_shape(rendered_skill):
    cards = build_cards(rendered_skill.parent.parent)
    assert cards
    card = cards[0]
    for key in ("name", "effect", "path", "skill_md_hash", "source_urls"):
        assert key in card
    assert card["skill_md_hash"] and len(card["skill_md_hash"]) == 64


def test_server_routes(rendered_skill):
    server, base = serve_skills(rendered_skill.parent.parent)
    try:
        with urllib.request.urlopen(f"{base}/healthz", timeout=5) as resp:
            assert json.loads(resp.read()) == {"status": "ok"}
        with urllib.request.urlopen(f"{base}/skills") as resp:
            payload = json.loads(resp.read())
        assert payload["ok"] is True
        assert payload["skills"]
        card = payload["skills"][0]
        with urllib.request.urlopen(f"{base}/skills/{card['path']}/SKILL.md") as resp:
            assert b"# " in resp.read()
        try:
            with urllib.request.urlopen(f"{base}/skills/../etc/passwd") as resp:
                assert resp.status in (403, 404)
        except urllib.error.HTTPError as exc:
            assert exc.code in (403, 404)  # escape guard refuses traversal
    finally:
        server.shutdown()


def test_symlinked_index_and_files_are_refused(rendered_skill):
    # H4 hardening controls: a symlinked index and a symlinked package file
    # must not leak content through the read-only surface. Probes live in
    # their own directories so the session-scoped fixture is never mutated.
    skills = rendered_skill.parent.parent
    probe = skills / "LeakProbe"
    probe.mkdir()
    try:
        (skills / "real-index.json").write_text("{}", encoding="utf-8")
        index = skills / "index.json"
        index.symlink_to(skills / "real-index.json")
        outside = skills.parent / "outside-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = probe / "SKILL.md"
        link.symlink_to(outside)
        server, base = serve_skills(skills)
        try:
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(f"{base}/index.json", timeout=5)
            assert excinfo.value.code == 403
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(f"{base}/skills/LeakProbe/SKILL.md", timeout=5)
            assert excinfo.value.code == 403
        finally:
            server.shutdown()
            server.server_close()
    finally:
        (skills / "index.json").unlink(missing_ok=True)
        (skills / "real-index.json").unlink(missing_ok=True)


def test_raw_encoded_traversal_is_refused(rendered_skill):
    import http.client

    server, base = serve_skills(rendered_skill.parent.parent)
    host_port = base.split("//", 1)[1]
    try:
        conn = http.client.HTTPConnection(host_port, timeout=5)
        conn.request("GET", "/skills/%2e%2e/%2e%2e/secret.txt")
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 403
        conn.close()
    finally:
        server.shutdown()
        server.server_close()


def test_query_strings_are_stripped(rendered_skill):
    server, base = serve_skills(rendered_skill.parent.parent)
    try:
        payload = json.loads(urllib.request.urlopen(f"{base}/skills", timeout=5).read())
        card = payload["skills"][0]
        with urllib.request.urlopen(
            f"{base}/skills/{card['path']}/SKILL.md?raw=1", timeout=5
        ) as resp:
            assert b"# " in resp.read()
    finally:
        server.shutdown()
        server.server_close()


def test_oversized_file_is_refused(rendered_skill):
    from skillarum.serve import MAX_SERVE_BYTES

    skills = rendered_skill.parent.parent
    big = rendered_skill.parent / "BIG.md"
    big.write_text("x" * (MAX_SERVE_BYTES + 1), encoding="utf-8")
    server, base = serve_skills(skills)
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(
                f"{base}/skills/{rendered_skill.parent.name}/BIG.md", timeout=15
            )
        assert excinfo.value.code == 413
    finally:
        big.unlink(missing_ok=True)
        server.shutdown()
        server.server_close()


def test_serve_skills_binds_ephemeral_port(rendered_skill):
    from skillarum.serve import serve_skills

    server, base_url = serve_skills(rendered_skill.parent.parent)
    try:
        assert server.server_address[1] > 0
    finally:
        server.shutdown()
        server.server_close()


def _wait_healthz(url: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(0.2)
    raise AssertionError(f"server never became healthy: {last}")


def test_cli_serve_subprocess_ephemeral_port(tmp_path):
    skills = tmp_path / "skills"
    package = skills / "demo"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\nname: demo\n---\n\n# Demo\n", encoding="utf-8"
    )
    (package / "manifest.json").write_text(
        json.dumps({"skill_name": "demo"}), encoding="utf-8"
    )
    repo_src = Path(__file__).resolve().parents[1] / "src"
    env = dict(os.environ, PYTHONPATH=str(repo_src))
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "skillarum",
            "serve",
            "--skills-dir",
            str(skills),
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        line = proc.stdout.readline()
        assert "http://" in line, (
            f"no bound URL logged: {line!r} "
            f"rc={proc.poll()} stderr={proc.stderr.read()!r}"
        )
        base = line.split("http://", 1)[1].split()[0]
        base_url = f"http://{base}"
        assert _wait_healthz(f"{base_url}/healthz") == {"status": "ok"}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
