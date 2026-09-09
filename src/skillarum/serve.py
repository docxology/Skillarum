"""Read-only HTTP discovery surface over rendered skills.

Adopted from husk's serving model, restricted to read-only GET routes:
Skillarum never executes generated content, so invoke semantics are
deliberately out of scope (documented in docs/v1-boundary.md). Responses are
size-bounded (``MAX_SERVE_BYTES``) and paths are query-stripped and
percent-decoded before the containment guard resolves them.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

# Response payload cap for single served files; discovery artifacts are two
# orders of magnitude smaller, so exceeding it signals a non-discovery file.
MAX_SERVE_BYTES = 16 * 1024 * 1024


def build_cards(skills_dir: str | Path) -> list[dict[str, Any]]:
    """Index-card schema for harness discovery: identity + integrity + provenance."""
    root = Path(skills_dir)
    cards: list[dict[str, Any]] = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        rel = manifest_path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue  # non-strict loading: malformed packages are skipped
        skill_path = manifest_path.parent / "SKILL.md"
        if not skill_path.is_file():
            continue
        from .render import validate_skill_package

        try:
            validate_skill_package(skill_path)
        except (OSError, ValueError):
            continue  # discovery omits packages whose current bytes fail validation
        cards.append(
            {
                "name": manifest.get("skill_name", manifest_path.parent.name),
                "effect": manifest.get("effect"),
                "area": manifest.get("area", ""),
                "path": manifest_path.parent.relative_to(root).as_posix(),
                "skill_md_hash": manifest.get("skill_sha256"),
                "source_urls": manifest.get("source_urls", []),
                "generator": manifest.get("generator"),
            }
        )
    return cards


def make_handler(skills_dir: str | Path) -> type[BaseHTTPRequestHandler]:
    """Build a GET-only, read-only request handler bound to one skills root."""
    root = Path(skills_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass  # keep test output clean

        def _send_json(self, code: int, obj: dict[str, Any]) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - stdlib naming convention
            path = unquote(urlsplit(self.path).path)
            if path in {"/", "/skills"}:
                self._send_json(200, {"ok": True, "skills": build_cards(root)})
            elif path == "/index.json":
                index = root / "index.json"
                if index.is_symlink():
                    self._send_json(403, {"error": "index must not be a symlink"})
                elif index.is_file():
                    if index.stat().st_size > MAX_SERVE_BYTES:
                        self._send_json(
                            413, {"error": "index exceeds the response size cap"}
                        )
                    else:
                        self._send_bytes(200, index.read_bytes(), "application/json")
                else:
                    self._send_json(404, {"error": "no index built"})
            elif path == "/healthz":
                self._send_json(200, {"status": "ok"})
            elif path.startswith("/skills/"):
                rel = path.removeprefix("/skills/").lstrip("/")
                target = (root / rel).resolve()
                if root not in target.parents and target != root:
                    self._send_json(403, {"error": "path escapes skills root"})
                elif not target.is_file():
                    self._send_json(404, {"error": "not found"})
                elif target.stat().st_size > MAX_SERVE_BYTES:
                    self._send_json(
                        413, {"error": "file exceeds the response size cap"}
                    )
                else:
                    self._send_bytes(
                        200, target.read_bytes(), "text/plain; charset=utf-8"
                    )
            else:
                self._send_json(404, {"error": "not found"})

    return Handler


def serve_skills(
    skills_dir: str | Path, host: str = "127.0.0.1", port: int = 0
) -> tuple[ThreadingHTTPServer, str]:
    """Start a read-only server; returns (server, base_url). Caller must shutdown()."""
    server = ThreadingHTTPServer((host, port), make_handler(skills_dir))
    server.daemon_threads = True
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    bound_host, bound_port = server.server_address[:2]
    return server, f"http://{bound_host}:{bound_port}"
