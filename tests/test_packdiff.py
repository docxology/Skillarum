"""Test package diff functionality."""

from __future__ import annotations

from pathlib import Path


from skillarum.packdiff import diff_packages, skill_sections


def test_skill_sections_splits_on_top_level_headers() -> None:
    """Split SKILL.md into sections by # headers."""
    text = """preamble text

# First Section

first content

# Second Section

second content
"""
    sections = skill_sections(text)
    assert "(preamble)" in sections
    assert "First Section" in sections
    assert "Second Section" in sections
    assert "first content" in sections["First Section"]
    assert "preamble text" in sections["(preamble)"]


def test_diff_packages_reports_added_removed_changed(tmp_path: Path) -> None:
    """Package diff detects file-level changes via SHA-256."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "SKILL.md").write_text("# Old Skill")
    (old_dir / "common.txt").write_text("same")
    (new_dir / "SKILL.md").write_text("# New Skill")
    (new_dir / "common.txt").write_text("same")
    (new_dir / "added.txt").write_text("new file")

    diff = diff_packages(old_dir, new_dir)
    assert diff.added == ("added.txt",)
    assert diff.changed == ("SKILL.md",)
    assert diff.unchanged_count == 1


def test_diff_packages_includes_skill_section_diff(tmp_path: Path) -> None:
    """SKILL.md changes include section-level diff for granular inspection."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    old_skill = """---
name: Test
---

# First Section
old content

# Common Section
unchanged
"""
    new_skill = """---
name: Test
---

# First Section
new content

# Common Section
unchanged

# Added Section
new section
"""
    (old_dir / "SKILL.md").write_text(old_skill)
    (new_dir / "SKILL.md").write_text(new_skill)

    diff = diff_packages(old_dir, new_dir)
    assert "First Section" in diff.skill_section_changes
    assert diff.skill_section_changes["First Section"]["status"] == "changed"
    assert "Added Section" in diff.skill_section_changes
    assert diff.skill_section_changes["Added Section"]["status"] == "added"
    assert (
        "Common Section" in diff.skill_section_changes
    )  # detected due to context change
    assert diff.skill_unified_diff
    assert "+new content" in diff.skill_unified_diff


def test_diff_packages_identical_when_no_changes(tmp_path: Path) -> None:
    """Package diff correctly reports identical directories."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "SKILL.md").write_text("# Same")
    (new_dir / "SKILL.md").write_text("# Same")

    diff = diff_packages(old_dir, new_dir)
    payload = diff.to_dict()
    assert payload["identical"]
    assert not payload["added"]
    assert not payload["removed"]
    assert not payload["changed"]


def test_diff_packages_handles_missing_skill_file(tmp_path: Path) -> None:
    """Gracefully handle directories without SKILL.md."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "other.txt").write_text("data")
    (new_dir / "other.txt").write_text("modified")

    diff = diff_packages(old_dir, new_dir)
    assert diff.changed == ("other.txt",)
    assert not diff.skill_section_changes
    assert diff.skill_unified_diff is None
