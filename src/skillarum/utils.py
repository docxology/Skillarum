"""Small pure helpers shared by the pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:  # POSIX is the supported v1 runtime; keep importable on other platforms.
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX platforms.
    fcntl = None  # type: ignore[assignment]


def slugify(value: str) -> str:
    """Return a stable filesystem-safe slug."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "skill"


def artifact_name(value: str) -> str:
    """Return a readable, case-preserving artifact directory name."""
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return normalized.strip("-._") or "Skill"


def is_safe_artifact_label(value: str) -> bool:
    """Return whether a human-facing label can safely identify an artifact area."""
    return bool(
        value
        and value == value.strip()
        and value not in {".", ".."}
        and not value.startswith((".", "-"))
        and not value.endswith((".", "-"))
        and any(character.isalnum() for character in value)
        and all(character.isalnum() or character in " ._-" for character in value)
    )


def is_sha256_hex(value: Any) -> bool:
    """Return whether a value is a complete lowercase/uppercase SHA-256 digest."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def sha256_text(value: str) -> str:
    """Hash UTF-8 text for provenance and cache keys."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Hash response content bytes for source provenance.

    The streaming fetcher hashes the decoded body it stores, so the digest is
    stable across transfer encodings (e.g. gzip vs identity).
    """
    return hashlib.sha256(value).hexdigest()


def stable_json(value: Any) -> str:
    """Serialize JSON-compatible data canonically for fingerprints."""
    return json.dumps(
        jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    """Return a stable hash for JSON-compatible data."""
    return sha256_text(stable_json(value))


def provenance_path(path: Path, base: Path | None = None) -> str:
    """Return a portable provenance path for a published artifact.

    Provenance records ship inside published archives, so they must never
    embed machine-specific absolute paths. When ``base`` is the generation
    root holding the record and its target as siblings (for figures, the
    parent of the figures directory), a target under it is recorded
    generation-root-relative so the reference resolves identically in the
    checkout and inside an archive whose member root is the generation root.
    Targets outside ``base`` fall back to the repository root (the package
    installation tree), then the working directory; a ``base``-relative form
    is the last resort with ``base``, and the absolute POSIX form is only
    reachable without ``base`` (test fixtures and foreign roots).
    """
    resolved = path.resolve()
    generation_root = base.resolve() if base is not None else None
    if generation_root is not None:
        try:
            return resolved.relative_to(generation_root).as_posix()
        except ValueError:
            pass
    for anchor in (Path(__file__).resolve().parents[2], Path.cwd().resolve()):
        try:
            return resolved.relative_to(anchor).as_posix()
        except ValueError:
            continue
    if generation_root is not None:
        return Path(os.path.relpath(resolved, generation_root)).as_posix()
    return resolved.as_posix()


def write_text_atomic(path: str | Path, text: str) -> None:
    """Replace a text file atomically after writing it in the same directory."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def write_bytes_atomic(path: str | Path, content: bytes) -> None:
    """Replace a binary file atomically after fsyncing its temporary payload."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def write_json_atomic(path: str | Path, value: Any) -> None:
    """Write deterministic, human-readable JSON atomically."""
    write_text_atomic(
        path,
        json.dumps(jsonable(value), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
    )


@contextmanager
def interprocess_lock(path: str | Path):
    """Hold an advisory per-target lock for the complete pipeline transaction."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def jsonable(value: Any) -> Any:
    """Convert common dataclass values into JSON-safe values."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value
