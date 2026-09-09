"""Detached SHA-256 pack signatures for packed skill zips.

A pack checksum records the self-asserted label of the packer and a deterministic
``pack_hash`` computed from the canonical manifest of archive members. The
signature is stored inside the archive as ``skillarum.sig`` so it travels with
the pack while remaining verifiable from the archive contents alone.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import is_sha256_hex, sha256_json

SIGNATURE_MEMBER = "skillarum.sig"
SIGNATURE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PackSignature:
    """A checksum statement about archive contents; it does not authenticate a signer."""

    schema_version: int
    packer: str
    signed_at: str
    pack_hash: str
    member_count: int
    members: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "packer": self.packer,
            "signed_at": self.signed_at,
            "pack_hash": self.pack_hash,
            "member_count": self.member_count,
            "members": dict(sorted(self.members.items())),
        }


def _member_manifest(archive_path: Path) -> dict[str, str]:
    """Hash every non-signature member of a zip archive deterministically.

    Duplicate member names are rejected: positional readers resolve the first
    entry while ``ZipFile.read`` resolves the last, so a duplicated member
    makes the archive ambiguous and must never be signed or verified.
    """
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = [
            info.filename
            for info in zf.infolist()
            if not info.is_dir() and info.filename != SIGNATURE_MEMBER
        ]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate archive member names: {duplicates}")
        return {name: hashlib.sha256(zf.read(name)).hexdigest() for name in names}


def build_signature(
    archive_path: Path,
    *,
    packer: str,
    signed_at: str | None = None,
) -> PackSignature:
    """Build a signature from the current contents of a packed zip."""
    members = _member_manifest(archive_path)
    payload = {
        "schema_version": SIGNATURE_SCHEMA_VERSION,
        "packer": packer,
        "signed_at": signed_at or datetime.now(timezone.utc).isoformat(),
        "member_count": len(members),
        "members": members,
    }
    return PackSignature(
        schema_version=SIGNATURE_SCHEMA_VERSION,
        packer=packer,
        signed_at=payload["signed_at"],
        pack_hash=sha256_json(payload),
        member_count=len(members),
        members=members,
    )


def write_signature(
    archive_path: Path,
    *,
    packer: str,
    signed_at: str | None = None,
) -> PackSignature:
    """Add (or replace) the ``skillarum.sig`` member inside a packed zip.

    The rewrite is performed on a temporary sibling and moved into place, so a
    failure never leaves a half-written archive.
    """
    signature = build_signature(archive_path, packer=packer, signed_at=signed_at)
    temp_path = archive_path.with_suffix(archive_path.suffix + ".tmp-sig")
    try:
        with (
            zipfile.ZipFile(archive_path, "r") as src,
            zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as dst,
        ):
            for info in src.infolist():
                if info.filename == SIGNATURE_MEMBER or info.is_dir():
                    continue
                dst.writestr(info, src.read(info.filename))
            dst.writestr(
                SIGNATURE_MEMBER,
                json.dumps(signature.to_dict(), indent=2, sort_keys=True) + "\n",
            )
        temp_path.replace(archive_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return signature


def read_signature(archive_path: Path) -> PackSignature | None:
    """Read the signature member from a packed zip, if present."""
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            if SIGNATURE_MEMBER not in zf.namelist():
                return None
            payload = json.loads(zf.read(SIGNATURE_MEMBER).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    members = payload.get("members")
    if not isinstance(members, dict):
        return None
    if (
        type(payload.get("schema_version")) is not int
        or payload["schema_version"] != SIGNATURE_SCHEMA_VERSION
    ):
        return None
    if type(payload.get("member_count")) is not int or payload["member_count"] < 0:
        return None
    return PackSignature(
        schema_version=payload["schema_version"],
        packer=str(payload.get("packer", "")),
        signed_at=str(payload.get("signed_at", "")),
        pack_hash=str(payload.get("pack_hash", "")),
        member_count=int(payload.get("member_count", -1)),
        members={str(key): str(value) for key, value in members.items()},
    )


def verify_signature(
    archive_path: Path,
    *,
    expected_packer: str | None = None,
) -> dict[str, Any]:
    """Verify the detached signature of a packed zip.

    Returns a report with ``ok``, the recomputed pack hash, and any failures.
    A missing signature is a verification failure.
    """
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            readable = SIGNATURE_MEMBER in zf.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        return {
            "ok": False,
            "archive": str(archive_path),
            "error": f"unreadable archive: {exc}",
        }
    signature = read_signature(archive_path)
    if signature is None:
        if readable:
            return {
                "ok": False,
                "archive": str(archive_path),
                "error": f"unreadable {SIGNATURE_MEMBER} signature member",
            }
        return {
            "ok": False,
            "archive": str(archive_path),
            "error": f"missing {SIGNATURE_MEMBER} signature member",
        }
    failures: list[str] = []
    if not is_sha256_hex(signature.pack_hash):
        failures.append("pack_hash is not a sha256 hex digest")
    try:
        actual_members = _member_manifest(archive_path)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        failures.append(str(exc))
        actual_members = None
    if actual_members is not None and actual_members != signature.members:
        failures.append("member hashes do not match signature")
    if actual_members is not None and len(actual_members) != signature.member_count:
        failures.append("member count does not match signature")
    if expected_packer is not None and signature.packer != expected_packer:
        failures.append(f"packer mismatch: expected {expected_packer!r}")
    payload = {
        "schema_version": signature.schema_version,
        "packer": signature.packer,
        "signed_at": signature.signed_at,
        "member_count": signature.member_count,
        "members": signature.members,
    }
    recomputed = sha256_json(payload)
    if recomputed != signature.pack_hash:
        failures.append("pack_hash does not cover the recorded member manifest")
    return {
        "ok": not failures,
        "archive": str(archive_path),
        "pack_hash": signature.pack_hash,
        "recomputed_hash": recomputed,
        "packer": signature.packer,
        "member_count": signature.member_count,
        "failures": failures,
    }
