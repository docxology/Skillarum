"""Tests for deterministic effect floors and severity resolution."""

from __future__ import annotations

import pytest

from skillarum.models import PreparedCorpus, PreparedPage
from skillarum.render import effect_floor, resolve_effect


def _corpus(pages: list[dict], skill_name: str = "demo") -> PreparedCorpus:
    pages = tuple(
        PreparedPage(
            url=p["url"],
            title=p.get("title", ""),
            headings=(),
            text=p.get("text", ""),
            links=(),
        )
        for p in pages
    )
    return PreparedCorpus(
        profile_id="p",
        profile_name="P",
        target_id=skill_name,
        skill_name=skill_name,
        pages=pages,
        request_count=len(pages),
        profile_fingerprint="0" * 64,
    )


def test_readonly_floor_for_plain_docs():
    corpus = _corpus([{"url": "https://example.com/docs", "title": "Introduction"}])
    assert effect_floor(corpus) == "readonly"


def test_destructive_verb_in_title_floors_destructive():
    corpus = _corpus([{"url": "https://example.com/api", "title": "Delete a resource"}])
    assert effect_floor(corpus) == "destructive"


def test_mutating_url_hint_floors_mutating():
    corpus = _corpus([{"url": "https://example.com/admin/users", "title": "Users"}])
    assert effect_floor(corpus) == "mutating"


def test_resolve_effect_can_raise_but_not_lower():
    assert resolve_effect(None, "readonly") == "readonly"
    assert resolve_effect("mutating", "readonly") == "mutating"
    assert resolve_effect("readonly", "destructive") == "destructive"
    assert resolve_effect("destructive", "mutating") == "destructive"


def test_resolve_effect_rejects_unknown_tag():
    with pytest.raises(ValueError):
        resolve_effect("apocalyptic", "readonly")
