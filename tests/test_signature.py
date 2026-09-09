"""Test pack signatures functionality."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from skillarum.signature import (
    SIGNATURE_MEMBER,
    build_signature,
    read_signature,
    verify_signature,
    write_signature,
)


def test_write_and_read_signature(tmp_path: Path) -> None:
    """Build a minimal zip and add a valid signature."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "SKILL.md", "---\nname: Test\ndescription: Test skill\n---\n\n# Test\n"
        )
        zf.writestr("manifest.json", '{"schema_version": 2}')
    signature = write_signature(zip_path, packer="test-runner")
    assert signature.packer == "test-runner"
    assert signature.member_count == 2
    assert signature.pack_hash
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert SIGNATURE_MEMBER in zf.namelist()
    read_sig = read_signature(zip_path)
    assert read_sig
    assert read_sig.packer == "test-runner"
    assert read_sig.pack_hash == signature.pack_hash
    assert read_sig.member_count == 2
    report = verify_signature(zip_path)
    assert report["ok"]
    assert report["packer"] == "test-runner"


def test_signature_verifies_member_integrity(tmp_path: Path) -> None:
    """The signature fails when a member is modified."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SKILL.md", "original")
    write_signature(zip_path, packer="test")
    # Tamper by rewriting the member in place (not by appending a duplicate
    # name, which the duplicate-member control covers separately).
    with zipfile.ZipFile(zip_path, "r") as src:
        sig = src.read(SIGNATURE_MEMBER)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as dst:
        dst.writestr("SKILL.md", "tampered")
        dst.writestr(SIGNATURE_MEMBER, sig)
    report = verify_signature(tampered)
    assert not report["ok"]
    assert any(
        "member hashes do not match" in failure for failure in report["failures"]
    )


def test_signature_fails_with_expected_packer_mismatch(tmp_path: Path) -> None:
    """The verification fails when packer does not match expectation."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy", "data")
    write_signature(zip_path, packer="alice")
    report = verify_signature(zip_path, expected_packer="bob")
    assert not report["ok"]
    assert any("packer mismatch" in failure for failure in report["failures"])


def test_missing_signature_fails_verification(tmp_path: Path) -> None:
    """Unsigned zips fail verification with a helpful error."""
    zip_path = tmp_path / "unsigned.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy", "data")
    report = verify_signature(zip_path)
    assert not report["ok"]
    assert "missing skillarum.sig signature member" in report["error"]


def test_read_signature_returns_none_for_unsigned_zip(tmp_path: Path) -> None:
    """read_signature gracefully handles unsigned archives."""
    zip_path = tmp_path / "unsigned.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy", "data")
    assert read_signature(zip_path) is None


def test_build_signature_excludes_signature_member(tmp_path: Path) -> None:
    """Signatures are built from the non-signature members only."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SKILL.md", "data")
        zf.writestr(SIGNATURE_MEMBER, "old signature")
    signature = build_signature(zip_path, packer="test")
    assert signature.member_count == 1
    assert SIGNATURE_MEMBER not in signature.members
    assert "SKILL.md" in signature.members


def test_signature_survives_rewrite(tmp_path: Path) -> None:
    """write_signature performs the temp-file rewrite correctly."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("original.txt", "data")
    first = write_signature(zip_path, packer="first")
    second = write_signature(zip_path, packer="second")
    assert first.pack_hash != second.pack_hash
    assert read_signature(zip_path).packer == "second"
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "original.txt" in zf.namelist()
        assert zf.read("original.txt") == b"data"


def test_read_signature_tolerates_malformed_payloads(tmp_path: Path) -> None:
    """read_signature returns None for malformed signature members."""
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SKILL.md", "data")
        zf.writestr(SIGNATURE_MEMBER, "not json")
    assert read_signature(zip_path) is None

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SKILL.md", "data")
        zf.writestr(SIGNATURE_MEMBER, "[not a dict]")
    assert read_signature(zip_path) is None


def test_build_signature_refuses_duplicate_members(tmp_path: Path) -> None:
    # F19: duplicate member names are ambiguous (readers resolve the first
    # entry, hashing resolves the last), so signatures must refuse to cover
    # them instead of silently deduplicating.
    zip_path = tmp_path / "dupe-build.zip"
    with zipfile.ZipFile(zip_path, "w") as writer:
        writer.writestr("a.txt", "1")
        writer.writestr("a.txt", "2")
    with pytest.raises(ValueError, match="duplicate"):
        build_signature(zip_path, packer="test-runner")


def test_verify_rejects_duplicate_member_names(tmp_path: Path) -> None:
    # F19 exploit control: prepending a same-name attacker entry before the
    # benign one keeps dict-based hashing on the benign copy while positional
    # readers extract the attacker payload. Verification must fail instead.
    zip_path = tmp_path / "signed.zip"
    with zipfile.ZipFile(zip_path, "w") as writer:
        writer.writestr("benign.txt", "benign payload")
    write_signature(zip_path, packer="test-runner")
    with zipfile.ZipFile(zip_path, "r") as src:
        benign = src.read("benign.txt")
        sig = src.read(SIGNATURE_MEMBER)
        infos = [i for i in src.infolist() if not i.is_dir()]
    forged = tmp_path / "forged.zip"
    with zipfile.ZipFile(forged, "w") as dst:
        dst.writestr("benign.txt", "attacker payload")
        for info in infos:
            dst.writestr(info, benign if info.filename == "benign.txt" else sig)
    report = verify_signature(forged)
    assert report["ok"] is False
    assert any("duplicate" in failure for failure in report["failures"])


def test_verify_reports_unreadable_archive(tmp_path: Path) -> None:
    # A corrupt archive is not a missing signature: the report must say the
    # archive itself is unreadable.
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not a zip at all")
    report = verify_signature(corrupt)
    assert report["ok"] is False
    assert "unreadable" in report["error"]
