"""Hash-level and section-level comparison of rendered skill packages."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILL_DOC = "SKILL.md"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_tree(root: Path) -> dict[str, str]:
    """Map relative artifact paths to sha256 hashes for every file under root."""
    artifacts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            artifacts[path.relative_to(root).as_posix()] = _sha256_bytes(
                path.read_bytes()
            )
    return artifacts


def skill_sections(text: str) -> dict[str, str]:
    """Split SKILL.md content into top-level ``# `` sections."""
    sections: dict[str, str] = {}
    current_title = "(preamble)"
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("# ") and not line.startswith("#!"):
            sections[current_title] = "".join(lines)
            current_title = line.strip().lstrip("# ").strip()
            lines = [line]
        else:
            lines.append(line)
    sections[current_title] = "".join(lines)
    return sections


@dataclass(frozen=True)
class PackageDiff:
    """Comparison of two rendered skill packages at hash level."""

    old_path: str
    new_path: str
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    unchanged_count: int = 0
    old_hashes: dict[str, str] = field(default_factory=dict)
    new_hashes: dict[str, str] = field(default_factory=dict)
    skill_section_changes: dict[str, dict[str, Any]] = field(default_factory=dict)
    skill_unified_diff: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_path": self.old_path,
            "new_path": self.new_path,
            "identical": not (self.added or self.removed or self.changed),
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
            "unchanged_count": self.unchanged_count,
            "old_hashes": dict(sorted(self.old_hashes.items())),
            "new_hashes": dict(sorted(self.new_hashes.items())),
            "skill_section_changes": dict(sorted(self.skill_section_changes.items())),
            "skill_unified_diff": self.skill_unified_diff,
        }


def diff_packages(old_dir: Path, new_dir: Path) -> PackageDiff:
    """Compare two rendered skill package directories.

    Hash level: every artifact is hashed and bucketed as added, removed, or
    changed. For SKILL.md, a section-level diff (per top-level ``# `` heading)
    and a unified text diff are included so operators see what moved inside
    the document, not just that it changed.
    """
    old_dir = Path(old_dir)
    new_dir = Path(new_dir)
    old_hashes = _hash_tree(old_dir)
    new_hashes = _hash_tree(new_dir)
    old_keys = set(old_hashes)
    new_keys = set(new_hashes)
    added = tuple(sorted(new_keys - old_keys))
    removed = tuple(sorted(old_keys - new_keys))
    changed = tuple(
        sorted(key for key in old_keys & new_keys if old_hashes[key] != new_hashes[key])
    )
    section_changes: dict[str, dict[str, Any]] = {}
    unified: str | None = None
    if SKILL_DOC in changed:
        old_text = (old_dir / SKILL_DOC).read_text(encoding="utf-8")
        new_text = (new_dir / SKILL_DOC).read_text(encoding="utf-8")
        old_sections = skill_sections(old_text)
        new_sections = skill_sections(new_text)
        for title in sorted(set(old_sections) | set(new_sections)):
            old_body = old_sections.get(title)
            new_body = new_sections.get(title)
            if old_body == new_body:
                continue
            section_changes[title] = {
                "status": (
                    "added"
                    if old_body is None
                    else "removed"
                    if new_body is None
                    else "changed"
                ),
                "old_sha256": (
                    None if old_body is None else _sha256_bytes(old_body.encode())
                ),
                "new_sha256": (
                    None if new_body is None else _sha256_bytes(new_body.encode())
                ),
            }
        unified = "".join(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"{old_dir / SKILL_DOC}",
                tofile=f"{new_dir / SKILL_DOC}",
            )
        )
    return PackageDiff(
        old_path=str(old_dir),
        new_path=str(new_dir),
        added=added,
        removed=removed,
        changed=changed,
        unchanged_count=len(old_keys & new_keys) - len(changed),
        old_hashes=old_hashes,
        new_hashes=new_hashes,
        skill_section_changes=section_changes,
        skill_unified_diff=unified,
    )
