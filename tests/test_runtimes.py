"""Tests for cross-runtime frontmatter compilation."""

from __future__ import annotations

import pytest

from skillarum.runtimes import RUNTIME_TARGETS, compile_frontmatter


def test_agentskills_keeps_all_supported_fields():
    fm = {
        "name": "demo",
        "description": "d",
        "metadata": {"skillarum_effect": "readonly"},
    }
    compiled, notes = compile_frontmatter(fm, "agentskills")
    assert compiled == fm
    assert notes == []


def test_claude_drops_effect_with_note():
    compiled, notes = compile_frontmatter(
        {"name": "demo", "description": "d", "effect": "mutating"}, "claude"
    )
    assert compiled == {"name": "demo", "description": "d"}
    assert any("effect" in note for note in notes)


def test_description_truncated_with_note():
    long_desc = "x" * 2000
    compiled, notes = compile_frontmatter(
        {"name": "n", "description": long_desc}, "codex"
    )
    assert len(compiled["description"]) == 1024
    assert any("truncated" in note for note in notes)


def test_name_truncated_with_note():
    compiled, notes = compile_frontmatter(
        {"name": "n" * 80, "description": "d"}, "codex"
    )
    assert compiled["name"] == "n" * 64
    assert notes == ["truncated field 'name' from 80 to 64 chars for codex"]


def test_note_wording_is_stable():
    # docs/runtimes.md pins the exact note formats as the caller's audit trail.
    _, notes = compile_frontmatter(
        {"name": "n", "description": "d", "effect": "e"}, "claude"
    )
    assert notes == ["dropped field 'effect' (not supported by claude)"]


def test_all_targets_share_the_documented_spec():
    for name, spec in RUNTIME_TARGETS.items():
        assert spec["allowed_fields"] == (
            "name",
            "description",
            "license",
            "allowed-tools",
            "metadata",
        )
        assert "allow_unicode" not in spec


def test_unknown_target_rejected():
    with pytest.raises(ValueError):
        compile_frontmatter({"name": "x"}, "skynet")


def test_all_targets_have_limits():
    for name, spec in RUNTIME_TARGETS.items():
        assert spec["name_max"] == 64
        assert spec["description_max"] == 1024
