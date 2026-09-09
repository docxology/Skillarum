"""Tests for quarantine-then-promote draft handling."""

from __future__ import annotations

import hashlib
import json

from skillarum.quarantine import (
    confirm_quarantined_draft,
    quarantine_refreshed_draft,
)


def _sha(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def test_quarantine_leaves_canonical_untouched(tmp_path):
    cache = tmp_path / "drafts" / "x.json"
    canonical = {"draft": {"body": "v1"}, "draft_sha256": "a" * 64}
    cache.parent.mkdir()
    cache.write_text(json.dumps(canonical), encoding="utf-8")

    refreshed = {"body": "refreshed body"}
    slot = quarantine_refreshed_draft(
        cache, refreshed, "f" * 64, canonical["draft_sha256"]
    )
    assert slot.is_file()
    record = json.loads(slot.read_text())
    assert record["confirmations"] == 1
    assert json.loads(cache.read_text())["draft"] == {"body": "v1"}  # canonical intact


def test_promotion_after_two_clean_confirmations(tmp_path):
    cache = tmp_path / "drafts" / "x.json"
    canonical = {"draft": {"body": "v1"}, "draft_sha256": "a" * 64}
    cache.parent.mkdir()
    cache.write_text(json.dumps(canonical))
    refreshed = {"body": "refreshed body"}
    refreshed_hash = "b" * 64
    slot = quarantine_refreshed_draft(
        cache,
        refreshed,
        refreshed_hash,
        canonical["draft_sha256"],
    )
    # Quarantine itself is confirmation 1; one clean confirm reaches threshold.
    first = confirm_quarantined_draft(cache, refreshed_hash)
    assert first["promoted"] is True
    assert first["confirmations"] == 2
    assert not slot.exists()
    promoted = json.loads(cache.read_text())
    assert promoted["draft"] == refreshed


def test_different_refresh_hash_discards_stale_slot(tmp_path):
    cache = tmp_path / "drafts" / "x.json"
    canonical = {"draft": {"body": "v1"}, "draft_sha256": "a" * 64}
    cache.parent.mkdir()
    cache.write_text(json.dumps(canonical))
    quarantine_refreshed_draft(cache, {"body": "r1"}, "f" * 64, "a" * 64)
    state = confirm_quarantined_draft(cache, "0" * 64)  # different hash
    assert state == {"promoted": False, "confirmations": 0, "stale": True}
    slot = tmp_path / "drafts" / "x.quarantine.json"
    assert not slot.exists()
    assert json.loads(cache.read_text())["draft"] == {"body": "v1"}


def test_promotion_after_hash_change_keeps_sha_bound_to_payload(tmp_path):
    """Negative control: the pre-fix code promoted old bytes under the new
    digest; promotion must pair payload bytes with their own sha256."""
    cache = tmp_path / "drafts" / "x.json"
    canonical = {"draft": {"body": "v1"}, "draft_sha256": "a" * 64}
    cache.parent.mkdir()
    cache.write_text(json.dumps(canonical))
    first_payload = {"body": "r1"}
    quarantine_refreshed_draft(cache, first_payload, "f" * 64, "a" * 64)
    stale = confirm_quarantined_draft(cache, "0" * 64)
    assert stale.get("stale") is True
    refreshed = {"body": "r2"}
    refreshed_hash = _sha(refreshed)
    quarantine_refreshed_draft(cache, refreshed, refreshed_hash, "a" * 64)
    state = confirm_quarantined_draft(cache, refreshed_hash)
    assert state["promoted"] is True
    promoted = json.loads(cache.read_text())
    assert promoted["draft"] == refreshed
    assert promoted["draft_sha256"] == refreshed_hash
    assert _sha(promoted["draft"]) == promoted["draft_sha256"]


def test_confirm_without_quarantine_is_noop(tmp_path):
    cache = tmp_path / "drafts" / "x.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({"draft": {}, "draft_sha256": "a"}))
    state = confirm_quarantined_draft(cache, "f" * 64)
    assert state == {"promoted": False, "confirmations": 0}
