"""Source-reference integrity: ``references/sources.json`` provenance binding.

Regression controls for the render defect where the manifest declared a hash
over a different JSON serialization than the bytes ``write_json_atomic``
actually wrote, and where ``validate_skill_package`` never inspected the
source-reference file, so deleting or tampering source provenance passed.

Every control mutates a real rendered package under ``tmp_path``; nothing is
mocked and nothing is read from ``output/``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from skillarum.generators import DeterministicGenerator
from skillarum.models import PreparedCorpus, PreparedPage
from skillarum.render import render_skill, validate_skill_package
from skillarum.utils import sha256_bytes, sha256_text

_SOURCES_RELATIVE = "references/sources.json"


def _corpus() -> PreparedCorpus:
    """Two-page corpus so provenance order is part of the binding."""
    return PreparedCorpus(
        profile_id="p",
        profile_name="P",
        profile_fingerprint="p-fingerprint",
        target_id="t",
        skill_name="Fixture-Skill",
        pages=(
            PreparedPage(
                url="https://example.org/page",
                title="Fixture",
                headings=("Intro",),
                text="Source text",
                links=(),
                requested_url="https://example.org/page",
                final_url="https://example.org/page",
                fetched_at="2026-09-01T00:00:00Z",
                status_code=200,
                content_sha256=sha256_text("Source text"),
            ),
            PreparedPage(
                url="https://example.org/other",
                title="Fixture Two",
                headings=("More",),
                text="Second source",
                links=(),
                requested_url="https://example.org/other",
                final_url="https://example.org/other",
                fetched_at="2026-09-01T00:00:05Z",
                status_code=200,
                content_sha256=sha256_text("Second source"),
            ),
        ),
    )


def _render(tmp_path: Path, *, name: str = "skills") -> Path:
    corpus = _corpus()
    return render_skill(
        DeterministicGenerator().generate(corpus), corpus, tmp_path / name
    )


def _manifest(path: Path) -> dict:
    return json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(path: Path, manifest: dict) -> None:
    (path.parent / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reforge(path: Path, mutate) -> None:
    """Rewrite sources.json with a mutated payload and a matching manifest hash.

    This is the self-consistent rehashed forgery: the declared hash is valid
    for the written bytes, so only provenance re-derivation can reject it.
    """
    sources = path.parent / _SOURCES_RELATIVE
    payload = json.loads(sources.read_text(encoding="utf-8"))
    mutate(payload)
    forged = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    sources.write_text(forged, encoding="utf-8")
    manifest = _manifest(path)
    manifest["artifact_hashes"][_SOURCES_RELATIVE] = sha256_bytes(
        forged.encode("utf-8")
    )
    _write_manifest(path, manifest)


def test_pristine_package_hashes_exact_written_bytes(tmp_path: Path) -> None:
    """The declared source-reference hash equals the bytes actually written."""
    path = _render(tmp_path)
    sources = path.parent / _SOURCES_RELATIVE
    declared = _manifest(path)["artifact_hashes"][_SOURCES_RELATIVE]
    assert declared == sha256_bytes(sources.read_bytes())
    # Guard the original defect: the legacy declaration hashed an
    # insertion-order json.dumps() payload, not the written bytes.
    corpus = _corpus()
    legacy_payload = {
        "schema": "skillarum.sources/v1",
        "profile_id": corpus.profile_id,
        "target_id": corpus.target_id,
        "sources": [
            {
                "url": page.url,
                "requested_url": page.requested_url or page.url,
                "final_url": page.final_url or page.url,
                "fetched_at": page.fetched_at,
                "status_code": page.status_code,
                "title": page.title,
                "content_sha256": page.content_sha256 or sha256_text(page.text),
                "truncated": page.truncated,
            }
            for page in corpus.pages
        ],
    }
    assert declared != sha256_text(json.dumps(legacy_payload))
    assert validate_skill_package(path)


def test_missing_source_reference_rejected(tmp_path: Path) -> None:
    """Deleting the source map must fail validation."""
    path = _render(tmp_path)
    (path.parent / _SOURCES_RELATIVE).unlink()
    with pytest.raises(ValueError, match="source map must be a regular file"):
        validate_skill_package(path)


def test_altered_source_reference_rejected(tmp_path: Path) -> None:
    """Edited source-map bytes no longer match the declared hash."""
    path = _render(tmp_path)
    sources = path.parent / _SOURCES_RELATIVE
    payload = json.loads(sources.read_text(encoding="utf-8"))
    payload["sources"][0]["url"] = "https://evil.example/page"
    sources.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source reference hash does not match"):
        validate_skill_package(path)


@pytest.mark.parametrize(
    "declared", [None, "tampered", "deadbeef"], ids=["absent", "nonhex", "short"]
)
def test_declared_source_reference_hash_must_be_sha256(
    tmp_path: Path, declared: str | None
) -> None:
    """The manifest must carry a complete SHA-256 hash for the source map."""
    path = _render(tmp_path)
    manifest = _manifest(path)
    if declared is None:
        manifest["artifact_hashes"].pop(_SOURCES_RELATIVE)
    else:
        manifest["artifact_hashes"][_SOURCES_RELATIVE] = declared
    _write_manifest(path, manifest)
    with pytest.raises(ValueError, match="must declare a SHA-256 artifact hash"):
        validate_skill_package(path)


def test_source_reference_symlink_rejected(tmp_path: Path) -> None:
    """A symlinked source map is rejected even when its bytes are valid."""
    path = _render(tmp_path)
    sources = path.parent / _SOURCES_RELATIVE
    outside = tmp_path / "outside" / "sources.json"
    outside.parent.mkdir()
    outside.write_bytes(sources.read_bytes())
    sources.unlink()
    sources.symlink_to(outside)
    with pytest.raises(ValueError, match="source map must be a regular file"):
        validate_skill_package(path)


def test_references_directory_symlink_rejected(tmp_path: Path) -> None:
    """A symlinked references/ directory must not host the package source map.

    The child file is a regular file with byte-identical content and a valid
    declared hash, so only the regular-directory rule keeps the whole source
    map inside the portable package.
    """
    path = _render(tmp_path)
    references = path.parent / "references"
    outside = tmp_path / "outside-references"
    outside.mkdir()
    shutil.copy2(references / "sources.json", outside / "sources.json")
    shutil.rmtree(references)
    references.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="references directory must be a regular"):
        validate_skill_package(path)


def test_rehashed_forgery_rejected_by_provenance_binding(tmp_path: Path) -> None:
    """A changed URL is rejected even when the caller recomputes the hash."""
    path = _render(tmp_path)
    _reforge(
        path,
        lambda payload: payload["sources"][0].__setitem__(
            "url", "https://evil.example/page"
        ),
    )
    with pytest.raises(ValueError, match="does not match manifest provenance"):
        validate_skill_package(path)


def test_reordered_source_entries_rejected(tmp_path: Path) -> None:
    """Source-map provenance order is bound to manifest page order."""
    path = _render(tmp_path)
    _reforge(path, lambda payload: payload["sources"].reverse())
    with pytest.raises(ValueError, match="does not match manifest provenance"):
        validate_skill_package(path)


def test_identity_drift_rejected(tmp_path: Path) -> None:
    """A changed profile identity is rejected even when rehashed."""
    path = _render(tmp_path)
    _reforge(path, lambda payload: payload.__setitem__("profile_id", "forged"))
    with pytest.raises(ValueError, match="identity does not match manifest"):
        validate_skill_package(path)


def test_malformed_json_rejected_even_rehashed(tmp_path: Path) -> None:
    """Unparseable source-map bytes fail validation even with a valid hash."""
    path = _render(tmp_path)
    sources = path.parent / _SOURCES_RELATIVE
    sources.write_bytes(b"{not json at all")
    manifest = _manifest(path)
    manifest["artifact_hashes"][_SOURCES_RELATIVE] = sha256_bytes(sources.read_bytes())
    _write_manifest(path, manifest)
    with pytest.raises(ValueError, match="invalid source reference JSON"):
        validate_skill_package(path)


def test_oversize_source_reference_hits_read_bound(tmp_path: Path) -> None:
    """Oversized source maps fail loudly instead of being read whole."""
    path = _render(tmp_path)
    sources = path.parent / _SOURCES_RELATIVE
    sources.write_bytes(sources.read_bytes() + b"x" * (16_000_000 + 1))
    manifest = _manifest(path)
    manifest["artifact_hashes"][_SOURCES_RELATIVE] = sha256_bytes(sources.read_bytes())
    _write_manifest(path, manifest)
    with pytest.raises(ValueError, match="validation read bound"):
        validate_skill_package(path)


def test_schema1_package_does_not_require_source_reference(tmp_path: Path) -> None:
    """Explicit legacy schema-1 packages stay valid without a source map."""
    path = _render(tmp_path)
    manifest = _manifest(path)
    manifest["schema_version"] = 1
    manifest["skill_format"] = "SKILL.md/v1"
    for field in (
        "run_id",
        "cache_identity",
        "generator_fingerprint",
        "generation_trace",
        "request_events",
        "artifact_hashes",
    ):
        manifest.pop(field, None)
    _write_manifest(path, manifest)
    shutil.rmtree(path.parent / "references")
    assert validate_skill_package(path)
