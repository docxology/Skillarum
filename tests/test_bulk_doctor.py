"""Test bulk profile validation via doctor --profile patterns."""

from __future__ import annotations

from pathlib import Path


from skillarum.cli import main


def test_doctor_bulk_profile_validation(tmp_path: Path) -> None:
    """Test doctor with multiple profiles via glob patterns."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "valid.yaml").write_text(
        """id: valid
name: Valid Profile
base_url: http://example.com
targets:
  - id: test
    name: Test Target
    urls: ["/test"]
"""
    )
    (profiles_dir / "invalid.yaml").write_text(
        "id: broken\n- missing colons\n  structure"
    )
    (profiles_dir / "good.yaml").write_text(
        """id: good
name: Good Profile  
base_url: https://example.org
targets:
  - id: good
    name: Good
    urls: ["/good"]
"""
    )

    # Test glob pattern matching
    # --no-network keeps exit codes decidable without a live Ollama endpoint
    # (an unreachable endpoint is exit 3 per docs/operations.md).
    code = main(
        ["doctor", "--profile", str(profiles_dir / "*.yaml"), "--json", "--no-network"]
    )
    assert code == 1  # invalid profile is a validation failure

    # Test individual profiles
    assert (
        main(
            [
                "doctor",
                "--profile",
                str(profiles_dir / "valid.yaml"),
                "--json",
                "--no-network",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "doctor",
                "--profile",
                str(profiles_dir / "invalid.yaml"),
                "--json",
                "--no-network",
            ]
        )
        == 1
    )


def test_doctor_reports_profile_health_table(tmp_path: Path, capsys) -> None:
    """Test doctor human output includes profile health table."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "valid.yaml").write_text(
        """id: valid
name: Valid Profile
base_url: http://example.com
targets:
  - id: test
    name: Test Target
    urls: ["/test"]
"""
    )
    (profiles_dir / "broken.yaml").write_text("invalid: yaml: content:")

    main(
        [
            "doctor",
            "--profile",
            str(profiles_dir / "valid.yaml"),
            "--profile",
            str(profiles_dir / "broken.yaml"),
            "--no-network",
        ]
    )
    captured = capsys.readouterr()
    assert "profile health:" in captured.out
    assert "status" in captured.out
    assert "valid" in captured.out
    assert "FAIL" in captured.out


def test_doctor_with_no_profiles_skips_table(tmp_path: Path, capsys) -> None:
    """Doctor without profiles should work normally without profile table."""
    code = main(["doctor", "--no-network"])
    capsys.readouterr()
    assert code == 0
    # Profile health section now always shows, even when empty


def test_doctor_glob_expansion_works(tmp_path: Path) -> None:
    """Test that glob patterns expand to multiple profile files."""
    profiles_dir = tmp_path / "sources"
    profiles_dir.mkdir()

    for name in ["alpha", "beta", "gamma"]:
        (profiles_dir / f"{name}.yaml").write_text(
            f"""id: {name}
name: {name.title()} Profile
base_url: http://example.com/{name}
targets:
  - id: page
    name: Page
    urls: ["/page"]
"""
        )

    code = main(
        ["doctor", "--profile", str(profiles_dir / "*.yaml"), "--json", "--no-network"]
    )
    assert code == 0  # All profiles should be valid
