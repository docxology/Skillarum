from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).parents[1]
ORCID = "0000-0001-6232-9096"


def test_author_doi_and_cover_metadata_are_complete() -> None:
    manuscript_config = next(
        candidate
        for candidate in (
            PROJECT_ROOT / "docs/manuscript/config.yaml",
            PROJECT_ROOT / "manuscript/config.yaml",
        )
        if candidate.is_file()
    )
    config = yaml.safe_load(manuscript_config.read_text(encoding="utf-8"))
    author = config["authors"][0]
    assert author == {
        "name": "Daniel Ari Friedman",
        "orcid": ORCID,
        "email": "daniel@activeinference.institute",
        "affiliation": "Active Inference Institute",
        "corresponding": True,
    }
    publication = config["publication"]
    # The release DOI is one value shared by every metadata surface; the test
    # checks agreement and Zenodo form rather than pinning a specific record.
    assert publication["doi"].startswith("10.5281/zenodo.")
    cff = yaml.safe_load((PROJECT_ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert cff["doi"] == publication["doi"]
    assert publication["doi"] in (PROJECT_ROOT / "README.md").read_text(
        encoding="utf-8"
    )
    assert publication["doi_status"] == "reserved"
    assert publication["doi_placeholder"] == (
        "DOI reserved for this release (registers on Zenodo publication)"
    )
    # These refer to published records and stay blank for a draft.
    assert publication["version_doi"] == ""
    assert publication["version_record"] == ""
    assert publication["github_repository"] == "docxology/Skillarum"
    assert publication["repository_url"] == "https://github.com/docxology/Skillarum"
    assert config["paper"]["cover"]["image"] == "cover/skillarum_cover.png"

    citation = yaml.safe_load(
        (PROJECT_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    )
    assert citation["repository-code"] == publication["repository_url"]
    assert citation["authors"][0]["orcid"] == f"https://orcid.org/{ORCID}"

    cover_manifest = yaml.safe_load(
        (PROJECT_ROOT / "data/cover.yaml").read_text(encoding="utf-8")
    )
    cover_path = PROJECT_ROOT / cover_manifest["artifact"]["path"]
    assert cover_path.is_file()
    assert (
        cover_manifest["artifact"]["sha256"]
        == hashlib.sha256(cover_path.read_bytes()).hexdigest()
    )
    assert cover_manifest["artifact"]["dimensions"] == "1024x1536"
    assert cover_manifest["artifact"]["text_in_image"] is False
    assert cover_manifest["alt_text"]
    assert cover_manifest["caption"]


def test_cff_and_config_metadata_agree() -> None:
    """Single-source-of-truth check: author-facing sidecars must not diverge."""
    config = yaml.safe_load(
        (PROJECT_ROOT / "docs/manuscript/config.yaml").read_text(encoding="utf-8")
    )
    citation = yaml.safe_load(
        (PROJECT_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    )
    assert citation["title"] == config["paper"]["title"]
    assert citation["version"] == config["paper"]["version"]
    assert citation["license"] == config["metadata"]["license"]
    assert (
        citation["authors"][0]["given-names"]
        + " "
        + citation["authors"][0]["family-names"]
        == config["authors"][0]["name"]
    )
