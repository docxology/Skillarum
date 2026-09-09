"""Quarantine-then-promote for refreshed skill drafts.

Adopted from skillwright: a refreshed draft that differs from the cached
canonical draft is quarantined for that run only; it becomes canonical only
after a second clean regeneration confirms it. A flaky or failed LLM
refresh can therefore never silently replace a good skill.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

QUARANTINE_SCHEMA = "skillarum.quarantine/v1"
CONFIRMATIONS_REQUIRED = 2


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def quarantine_slot_path(draft_cache_path: Path) -> Path:
    """Quarantine slot for one draft cache file (sibling .quarantine.json)."""
    return draft_cache_path.with_name(
        draft_cache_path.name.replace(".json", ".quarantine.json")
    )


def quarantine_refreshed_draft(
    draft_cache_path: Path,
    refreshed_payload: dict[str, Any],
    refreshed_payload_sha256: str,
    canonical_payload_sha256: str,
) -> Path:
    """Quarantine a divergent refreshed draft; the canonical cache is untouched."""
    slot = quarantine_slot_path(draft_cache_path)
    record = {
        "schema": QUARANTINE_SCHEMA,
        "canonical_draft_sha256": canonical_payload_sha256,
        "refreshed_draft_sha256": refreshed_payload_sha256,
        "confirmations": 1,
        "evidence_origin": "refresh",
        "refreshed_draft_payload": refreshed_payload,
        "refreshed_draft_payload_sha256": refreshed_payload_sha256,
    }
    _write_json(slot, record)
    return slot


def confirm_quarantined_draft(
    draft_cache_path: Path,
    refreshed_payload_sha256: str,
) -> dict[str, Any]:
    """Record one clean confirmation of the quarantined draft.

    At the required threshold the quarantined draft is promoted to canonical
    and the slot removed. Returns state with a ``promoted`` flag. A confirm
    whose hash no longer matches the quarantined payload is not a
    confirmation of anything: the slot is discarded as stale (``stale:
    True``) and the caller must re-quarantine the new payload, so promotion
    can never pair one payload's bytes with another payload's digest.
    """
    slot = quarantine_slot_path(draft_cache_path)
    if not slot.is_file():
        return {"promoted": False, "confirmations": 0}
    record = _read_json(slot)
    if record.get("refreshed_draft_payload_sha256") != refreshed_payload_sha256:
        slot.unlink()
        return {"promoted": False, "confirmations": 0, "stale": True}
    record["confirmations"] = int(record.get("confirmations", 0)) + 1
    if record["confirmations"] >= CONFIRMATIONS_REQUIRED:
        canonical = _read_json(draft_cache_path)
        canonical["draft"] = record.pop("refreshed_draft_payload")
        canonical["draft_sha256"] = refreshed_payload_sha256
        _write_json(draft_cache_path, canonical)
        slot.unlink()
        record["promoted"] = True
        return record
    _write_json(slot, record)
    record["promoted"] = False
    return record
