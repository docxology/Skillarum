"""Install rendered skills into agent harness roots with drift tracking.

Adopted from attebury/skillpress: an install writes a sidecar manifest
recording canonical hashes; ``drift`` re-hashes both the canonical package
and installed copies and reports stable issue codes without mutating
anything (read-only repair-plan pattern).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .utils import sha256_bytes, sha256_text, interprocess_lock
import tempfile

INSTALL_MANIFEST_SCHEMA = "skillarum.install-manifest"
INSTALL_MANIFEST_VERSION = 1

_HARNESS_DIR_NAMES = {
    "codex": "." + "codex" + "/skills",
    "claude": "." + "claude" + "/skills",
    "agents": "." + "agents" + "/skills",
}


def harness_roots() -> dict[str, str]:
    """Public mapping of harness name -> skills root (relative to home)."""
    return dict(_HARNESS_DIR_NAMES)


def _tree_hash(package_dir: Path) -> str:
    """Stable hash over the whole package file tree (paths + contents)."""
    digest_parts: list[str] = []
    for file_path in sorted(package_dir.rglob("*")):
        if file_path.is_symlink():
            raise ValueError(f"package contains a symlink: {file_path}")
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(package_dir).as_posix()
        if rel == ".skillarum-install.json":
            continue
        digest_parts.append(f"{rel}:{sha256_bytes(file_path.read_bytes())}")
    return sha256_text("\n".join(digest_parts))


def install_skill(
    skill_path: str | Path,
    harness: str,
    *,
    home: Path | None = None,
) -> dict[str, Any]:
    """Copy a validated skill package into the harness skills root.

    Writes a sidecar install manifest recording canonical hashes for later
    drift detection. The destination directory is the portable frontmatter name,
    so refreshes replace the skill already discovered by the harness.
    """
    from .render import validate_skill_package

    skill_file = Path(skill_path)
    metadata = validate_skill_package(skill_file)
    package_dir = skill_file.resolve().parent
    if harness not in _HARNESS_DIR_NAMES:
        raise ValueError(
            f"unknown harness: {harness!r} (known: {sorted(_HARNESS_DIR_NAMES)})"
        )
    root = (home or Path.home()) / _HARNESS_DIR_NAMES[harness]
    portable = metadata["name"]
    # F17 negative control: a frontmatter name like "../../../Outside" must
    # never move the install destination outside the harness skills root.
    if (
        Path(portable).name != portable
        or portable in {".", ".."}
        or (root / portable).resolve().parent != root.resolve()
    ):
        raise ValueError(
            "skill frontmatter name is not a portable single-directory name: "
            f"{portable!r}"
        )
    destination = root / portable
    root.mkdir(parents=True, exist_ok=True)
    if (
        destination.resolve() == package_dir
        or destination.resolve() in package_dir.parents
    ):
        raise ValueError("installation destination overlaps canonical package")
    if destination.is_symlink():
        raise ValueError("installation destination must not be a symlink")
    source_hash = _tree_hash(package_dir)
    from .render import _publish_package

    with interprocess_lock(root / f".{destination.name}.install.lock"):
        staging = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.install-", dir=root)
        )
        try:
            shutil.copytree(package_dir, staging, dirs_exist_ok=True)
            validate_skill_package(staging / "SKILL.md", enforce_path_authority=False)
            installed_hash = _tree_hash(staging)
            if installed_hash != source_hash:
                raise ValueError("canonical package changed during installation")
            manifest = {
                "schema": INSTALL_MANIFEST_SCHEMA,
                "version": INSTALL_MANIFEST_VERSION,
                "harness": harness,
                "installed_path": str(destination / "SKILL.md"),
                "canonical_path": str(package_dir / "SKILL.md"),
                "skill_md_hash": sha256_bytes((staging / "SKILL.md").read_bytes()),
                "source_tree_hash": source_hash,
                "installed_tree_hash": installed_hash,
            }
            (staging / ".skillarum-install.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            _publish_package(staging, destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    return manifest


def drift_report(
    skill_path: str | Path,
    harness: str,
    *,
    home: Path | None = None,
) -> dict[str, Any]:
    """Read-only comparison of canonical vs installed package state.

    Issue codes: ``install_manifest_missing``, ``install_manifest_invalid``,
    ``installed_skill_missing``, ``installed_skill_drift``,
    ``installed_package_drift``, ``installed_package_symlink``,
    ``canonical_skill_drift``, ``canonical_package_symlink``. Never mutates.
    """
    skill_file = Path(skill_path)
    package_dir = skill_file.resolve().parent
    if harness not in _HARNESS_DIR_NAMES:
        raise ValueError(f"unknown harness: {harness!r}")
    from .render import validate_skill_file

    try:
        name = validate_skill_file(skill_file)["name"]
    except (OSError, ValueError):
        # A damaged or symlinked canonical file is drift evidence, not a
        # crash: installs place packages under their portable name, so fall
        # back to the directory name to locate the sidecar.
        name = package_dir.name
    destination = (home or Path.home()) / _HARNESS_DIR_NAMES[harness] / name
    sidecar = destination / ".skillarum-install.json"
    issues: list[dict[str, Any]] = []
    canonical_tree: str | None
    try:
        canonical_tree = _tree_hash(package_dir)
    except ValueError:
        canonical_tree = None
        issues.append(
            {
                "code": "canonical_package_symlink",
                "message": f"canonical package contains a symlink: {package_dir}",
                "action": "resync",
            }
        )
    if not sidecar.is_file():
        issues.append(
            {
                "code": "install_manifest_missing",
                "message": f"no install manifest at {sidecar}",
                "action": "resync",
            }
        )
        return {
            "ok": False,
            "skill": str(skill_file),
            "harness": harness,
            "canonical_tree_hash": canonical_tree,
            "issues": issues,
        }
    try:
        recorded = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(recorded, dict):
            raise ValueError("install manifest must be a mapping")
        for key in (
            "harness",
            "skill_md_hash",
            "source_tree_hash",
            "installed_tree_hash",
        ):
            if not isinstance(recorded.get(key), str) or not recorded[key]:
                raise ValueError(f"install manifest field missing or invalid: {key}")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        issues.append(
            {
                "code": "install_manifest_invalid",
                "message": f"unreadable install manifest at {sidecar}: {exc}",
                "action": "resync",
            }
        )
        return {
            "ok": False,
            "skill": str(skill_file),
            "harness": harness,
            "canonical_tree_hash": canonical_tree,
            "issues": issues,
        }
    if not (destination / "SKILL.md").is_file():
        issues.append(
            {
                "code": "installed_skill_missing",
                "message": f"installed SKILL.md missing at {destination}",
                "action": "resync",
            }
        )
    else:
        installed_hash = sha256_text(
            (destination / "SKILL.md").read_text(encoding="utf-8")
        )
        if installed_hash != recorded["skill_md_hash"]:
            issues.append(
                {
                    "code": "installed_skill_drift",
                    "message": "installed SKILL.md differs from install-time hash",
                    "action": "resync",
                }
            )
    try:
        installed_tree = _tree_hash(destination)
    except ValueError as exc:
        installed_tree = None
        issues.append(
            {
                "code": "installed_package_symlink",
                "message": str(exc),
                "action": "resync",
            }
        )
    if installed_tree is not None and installed_tree != recorded["installed_tree_hash"]:
        issues.append(
            {
                "code": "installed_package_drift",
                "message": "installed package files changed since install",
                "action": "resync",
            }
        )
    if canonical_tree is not None and recorded["source_tree_hash"] != canonical_tree:
        issues.append(
            {
                "code": "canonical_skill_drift",
                "message": "canonical package changed since install",
                "action": "resync",
            }
        )
    return {
        "ok": not issues,
        "skill": str(skill_file),
        "harness": harness,
        "canonical_tree_hash": canonical_tree,
        "recorded": recorded,
        "issues": issues,
    }
