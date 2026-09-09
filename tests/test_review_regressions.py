"""Adversarial controls for research, publication, and package lifecycle contracts."""

import json
from pathlib import Path

import pytest

from skillarum.cli import _parser, main
from skillarum.figures import generate_figures, validate_figure_registry
from skillarum.install import drift_report, install_skill
from skillarum.research import (
    ReviewRating,
    build_evaluation_report,
    extract_manuscript_citations,
    load_evaluation_report,
    numeric_summary,
    render_manuscript,
    review_summary,
    validate_publication_manifest,
    weighted_cohen_kappa,
    write_evaluation_report,
)
from skillarum.utils import sha256_json


def test_research_cli_defaults_use_canonical_manuscript():
    parser = _parser()
    assert parser.parse_args(["research", "validate"]).manuscript_dir == Path(
        "docs/manuscript"
    )
    assert parser.parse_args(
        ["research", "manuscript", "--evaluation", "report.json"]
    ).source_dir == Path("docs/manuscript")


def test_degenerate_kappa_is_undefined():
    assert weighted_cohen_kappa({"case": 4}, {"case": 4}) is None


@pytest.mark.parametrize("score", [True, 1.5, float("nan")])
def test_ordinal_scores_require_integers(score):
    with pytest.raises(ValueError, match="integer"):
        ReviewRating("case", "rater", score, 4, 4, 4, 4, 4)


def test_duplicate_ratings_rejected_by_summary_api():
    rating = ReviewRating("case", "rater", 4, 4, 4, 4, 4, 4)
    with pytest.raises(ValueError, match="unique"):
        review_summary((rating, rating))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_numeric_summary_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="finite"):
        numeric_summary([value])


def test_manifest_cannot_claim_missing_rendered_artifacts(tmp_path):
    path = tmp_path / "reports/publication-manifest.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_count": 0,
                "artifact_hashes": {},
                "rendered_counts": {"pdf": 1, "html": 1},
            }
        )
    )
    assert not validate_publication_manifest(path, require_rendered=True)["ok"]


def test_manuscript_excludes_status_and_guidance_citations(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "01_body.md").write_text("# Body\n\n[@real]\n")
    (source / "MANUSCRIPT_STATUS.md").write_text("# Internal status\n\n@internal\n")
    (source / "README.md").write_text("@guide\n")
    rendered = render_manuscript(
        source, tmp_path / "rendered", build_evaluation_report(())
    )
    assert [p.name for p in rendered] == ["01_body.md"]
    assert extract_manuscript_citations(source) == {"real"}


def test_empty_manuscript_cannot_render_successfully(tmp_path):
    with pytest.raises(ValueError, match="no Markdown"):
        render_manuscript(
            tmp_path / "missing", tmp_path / "out", build_evaluation_report(())
        )


def test_report_rejects_hash_valid_but_false_summary(tmp_path):
    report_path = write_evaluation_report(build_evaluation_report(()), tmp_path)
    payload = json.loads(report_path.read_text())
    payload["summary"]["observation_count"] = 100
    payload.pop("artifact_sha256")
    payload["artifact_sha256"] = sha256_json(payload)
    report_path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="summary"):
        load_evaluation_report(report_path)


def test_tampered_binary_figure_returns_failed_validation(tmp_path):
    report = build_evaluation_report(())
    data = write_evaluation_report(report, tmp_path)
    registry = generate_figures(report, tmp_path / "figures", source_data=data)
    entry = json.loads(registry.read_text())["figures"][0]
    artifact = registry.parent / entry["path"]
    assert artifact.suffix == ".png"
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    result = validate_figure_registry(registry)
    assert not result["ok"]
    assert any("hash mismatch" in error for error in result["errors"])


def test_install_drift_detects_companion_changes(rendered_skill, tmp_path):
    manifest = install_skill(rendered_skill, "agents", home=tmp_path)
    installed = Path(manifest["installed_path"]).parent
    (installed / "manifest.json").write_text("{}")
    assert not drift_report(rendered_skill, "agents", home=tmp_path)["ok"]


def test_install_handles_binary_assets(rendered_skill, tmp_path):
    import shutil

    package = tmp_path / "canonical" / rendered_skill.parent.name
    shutil.copytree(rendered_skill.parent, package)
    (package / "asset.bin").write_bytes(b"\x80\xff\x00")
    installed = install_skill(package / "SKILL.md", "agents", home=tmp_path / "home")
    assert (
        Path(installed["installed_path"]).parent / "asset.bin"
    ).read_bytes() == b"\x80\xff\x00"


def test_live_flag_without_acquisition_does_not_promote_history(
    tmp_path, fixture_server, capsys
):
    profile = tmp_path / "fixture.yaml"
    profile.write_text(
        f"id: local\nname: Local\nbase_url: {fixture_server}\ncrawl:\n  allow_private_hosts: true\n  requests_per_second: 1000\ntargets:\n  - id: page\n    name: Page\n    urls: ['/page']\n"
    )
    output = tmp_path / "out"
    assert (
        main(
            [
                "evaluate",
                "--profile",
                str(profile),
                "--output-dir",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["evaluate", "--live", "--output-dir", str(output), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["summary"]["source_types"]["live"] == 0
    assert result["summary"]["source_types"]["fixture"] == 1


def test_discovery_rejects_tampered_package(rendered_skill, tmp_path):
    import shutil
    from skillarum.serve import build_cards

    package = tmp_path / rendered_skill.parent.name
    shutil.copytree(rendered_skill.parent, package)
    (package / "SKILL.md").write_text("tampered")
    assert build_cards(tmp_path) == []


def test_repo_fingerprint_changes_with_uncommitted_content(tmp_path):
    import subprocess
    from skillarum.repo_source import repo_fingerprint, repo_context_text

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    readme = tmp_path / "README.md"
    readme.write_text("# Original source narrative\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    before = repo_fingerprint(tmp_path)
    readme.write_text("# Changed source narrative\n")
    assert repo_fingerprint(tmp_path)["sha"] != before["sha"]
    assert "Changed source narrative" in repo_context_text(tmp_path)


def test_signature_malformed_integer_is_rejected(tmp_path):
    import zipfile
    from skillarum.signature import SIGNATURE_MEMBER, read_signature

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as writer:
        writer.writestr(
            SIGNATURE_MEMBER, json.dumps({"members": {}, "schema_version": "invalid"})
        )
    assert read_signature(archive) is None


def test_generated_frontmatter_uses_portable_extension_fields(rendered_skill):
    import yaml

    frontmatter = yaml.safe_load(rendered_skill.read_text().split("---", 2)[1])
    assert set(frontmatter) <= {
        "name",
        "description",
        "license",
        "allowed-tools",
        "metadata",
    }
    assert frontmatter["metadata"]["skillarum_effect"] in {
        "readonly",
        "mutating",
        "destructive",
    }
