"""Test the diff command via CLI."""

from __future__ import annotations

import json
from pathlib import Path


from skillarum.cli import main


def test_diff_command_reports_package_changes(tmp_path: Path) -> None:
    """skillarum diff compares two package directories and reports changes."""
    old_dir = tmp_path / "old_package"
    new_dir = tmp_path / "new_package"
    old_dir.mkdir()
    new_dir.mkdir()

    (old_dir / "SKILL.md").write_text("""---
name: Old Skill
description: Old description
---

# Old Skill

Old content here.

# Common Section

This stays the same.
""")
    (old_dir / "manifest.json").write_text('{"schema_version": 2}')

    (new_dir / "SKILL.md").write_text("""---
name: New Skill
description: Updated description
---

# New Skill

Updated content here.

# Common Section

This stays the same.

# Added Section

This is new content.
""")
    (new_dir / "manifest.json").write_text('{"schema_version": 2}')
    (new_dir / "new_file.txt").write_text("This is a new file.")

    # Test human-readable output
    code = main(["diff", str(old_dir), str(new_dir)])
    assert code == 1  # Should return 1 when packages differ

    # Test JSON output
    code = main(["diff", str(old_dir), str(new_dir), "--json"])
    assert code == 1


def test_diff_command_json_output(tmp_path: Path, capsys) -> None:
    """skillarum diff --json produces machine-readable output."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()

    (old_dir / "same.txt").write_text("unchanged")
    (old_dir / "removed.txt").write_text("will be removed")

    (new_dir / "same.txt").write_text("unchanged")
    (new_dir / "added.txt").write_text("new file")

    main(["diff", str(old_dir), str(new_dir), "--json"])
    captured = capsys.readouterr()

    output = json.loads(captured.out)
    assert not output["identical"]
    assert "added.txt" in output["added"]
    assert "removed.txt" in output["removed"]
    assert output["unchanged_count"] == 1


def test_diff_command_identical_packages_returns_zero(tmp_path: Path) -> None:
    """skillarum diff returns 0 when packages are identical."""
    old_dir = tmp_path / "package1"
    new_dir = tmp_path / "package2"
    old_dir.mkdir()
    new_dir.mkdir()

    (old_dir / "SKILL.md").write_text("# Same Content")
    (new_dir / "SKILL.md").write_text("# Same Content")

    code = main(["diff", str(old_dir), str(new_dir)])
    assert code == 0


def test_diff_command_shows_skill_section_changes(tmp_path: Path, capsys) -> None:
    """skillarum diff human output includes SKILL.md section-level changes."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()

    (old_dir / "SKILL.md").write_text("""---
name: Test
---

# Section A
old content

# Section B  
common content
""")

    (new_dir / "SKILL.md").write_text("""---
name: Test  
---

# Section A
new content

# Section B
common content

# Section C
added section
""")

    main(["diff", str(old_dir), str(new_dir)])
    captured = capsys.readouterr()

    assert "SKILL.md section changes:" in captured.out
    assert "[changed] Section A" in captured.out
    assert "[added] Section C" in captured.out
    assert "[changed] Section B" in captured.out  # detected due to diff context


def test_diff_command_handles_missing_directories() -> None:
    """skillarum diff handles missing directory arguments gracefully."""
    code = main(["diff", "/nonexistent/old", "/nonexistent/new"])
    assert code == 0  # Missing dirs treated as empty, shows identical
