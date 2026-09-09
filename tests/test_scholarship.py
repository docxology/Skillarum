from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from skillarum.cli import main
from skillarum.figures import generate_figures, validate_figure_registry
from skillarum.generators import DeterministicGenerator
from skillarum.models import (
    CrawlConfig,
    ExtractionConfig,
    PreparedCorpus,
    PreparedPage,
    SourceProfile,
    TargetSpec,
)
from skillarum.pipeline import run_profile
from skillarum.research import (
    ADDITIVE_SUMMARY_KEYS,
    AdjudicationRecord,
    ClaimRecord,
    CitationRecord,
    EvaluationCase,
    EvaluationObservation,
    ReviewRating,
    bootstrap_interval,
    build_evaluation_report,
    collect_observations,
    exact_binomial_interval,
    load_claims,
    load_citations,
    load_cases,
    load_adjudications,
    load_bibliography_keys,
    load_evaluation_report,
    load_ratings,
    manuscript_variables,
    numeric_summary,
    render_manuscript,
    review_summary,
    summarize_observations,
    validate_ledgers,
    validate_adjudications,
    validate_bibliography,
    extract_manuscript_citations,
    validate_publication_manifest,
    write_publication_manifest,
    validate_manuscript_tree,
    _run_provenance_matches,
    _is_iso_timestamp,
    weighted_cohen_kappa,
    write_evaluation_report,
    write_rating_template,
)
from skillarum.render import render_skill
from skillarum.utils import sha256_bytes, sha256_json, sha256_text


def _checkout_manuscript_dir() -> Path:
    """Canonical manuscript dir for this checkout, docs/manuscript/ first."""
    for candidate in (
        Path(__file__).resolve().parents[1] / "docs/manuscript",
        Path(__file__).resolve().parents[1] / "manuscript",
    ):
        if candidate.is_dir():
            return candidate
    raise AssertionError("no manuscript directory found in checkout")


def _fixture_corpus(skill_name: str = "Fixture-Skill") -> PreparedCorpus:
    """Create a valid acquired-like corpus without depending on ignored output."""
    text = "Fixture source text."
    page = PreparedPage(
        url="https://example.org/page",
        title="Fixture",
        headings=("Fixture",),
        text=text,
        links=(),
        requested_url="https://example.org/page",
        final_url="https://example.org/page",
        fetched_at="2026-01-01T00:00:00+00:00",
        status_code=200,
        content_sha256=sha256_text(text),
    )
    return PreparedCorpus(
        profile_id="fixture",
        profile_name="Fixture",
        target_id="fixture",
        skill_name=skill_name,
        pages=(page,),
    )


def test_research_contracts_and_ledgers(tmp_path: Path) -> None:
    citation = CitationRecord(
        citation_id="fixture-source",
        title="Fixture source",
        authors=("Tester",),
        year=2026,
        kind="source",
        url="https://example.org/source",
    )
    claim = ClaimRecord(
        claim_id="fixture-claim",
        text="The fixture is cited.",
        evidence_tier="source",
        status="supported",
        citation_ids=("fixture-source",),
    )
    assert CitationRecord.from_mapping(citation.to_dict()) == citation
    assert ClaimRecord.from_mapping(claim.to_dict()) == claim
    assert validate_ledgers((citation,), (claim,))["ok"]
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence", encoding="utf-8")
    artifact_claim = replace(claim, artifact_paths=("evidence.md",))
    assert validate_ledgers((citation,), (artifact_claim,), artifact_root=tmp_path)[
        "ok"
    ]
    unsafe_artifact = replace(claim, artifact_paths=("../outside.md",))
    assert not validate_ledgers(
        (citation,), (unsafe_artifact,), artifact_root=tmp_path
    )["ok"]
    missing_artifact = replace(claim, artifact_paths=("missing.md",))
    assert not validate_ledgers(
        (citation,), (missing_artifact,), artifact_root=tmp_path
    )["ok"]
    linked_artifact = tmp_path / "linked.md"
    linked_artifact.symlink_to(evidence)
    assert not validate_ledgers(
        (citation,),
        (replace(claim, artifact_paths=("linked.md",)),),
        artifact_root=tmp_path,
    )["ok"]
    assert not validate_ledgers(
        (citation,),
        (replace(claim, artifact_paths=(".cache/secret.json",)),),
        artifact_root=tmp_path,
    )["ok"]
    assert not validate_ledgers(
        (citation,),
        (replace(claim, artifact_paths=(str(evidence.resolve()),)),),
        artifact_root=tmp_path,
    )["ok"]
    bad = ClaimRecord(
        claim_id="pending",
        text="Not yet measured.",
        evidence_tier="pending",
        status="pending",
    )
    assert validate_ledgers((citation,), (bad,))["ok"]
    with pytest.raises(ValueError, match="absolute"):
        CitationRecord("bad", "Bad", (), 2026, "source", "/relative")
    with pytest.raises(ValueError, match="support"):
        ClaimRecord("bad", "Bad", "pending", "supported")
    with pytest.raises(ValueError, match="authors"):
        CitationRecord(
            "no-author", "No author", (), 2026, "paper", "https://example.org/no-author"
        )
    with pytest.raises(ValueError, match="ISO-8601"):
        CitationRecord(
            "bad-date",
            "Bad date",
            ("Tester",),
            2026,
            "paper",
            "https://example.org/date",
            accessed="yesterday",
        )
    with pytest.raises(ValueError, match="outside the supported range"):
        CitationRecord(
            "bad-year",
            "Bad year",
            ("Tester",),
            1899,
            "paper",
            "https://example.org/bad-year",
        )
    with pytest.raises(ValueError, match="unsupported evidence tier"):
        ClaimRecord("bad-tier", "Bad tier", "not-a-tier", "pending")
    with pytest.raises(ValueError, match="unsupported claim status"):
        ClaimRecord("bad-status", "Bad status", "source", "not-a-status")
    with pytest.raises(ValueError, match="criterion"):
        AdjudicationRecord(
            "case",
            "not-a-criterion",
            ("r1", "r2"),
            3,
            "editor",
            "reason",
            ("https://example.org/evidence",),
        )
    with pytest.raises(ValueError, match="final_score"):
        AdjudicationRecord(
            "case",
            "safety",
            ("r1", "r2"),
            5,
            "editor",
            "reason",
            ("https://example.org/evidence",),
        )
    with pytest.raises(ValueError, match="rationale"):
        AdjudicationRecord(
            "case",
            "safety",
            ("r1", "r2"),
            3,
            "editor",
            "",
            ("https://example.org/evidence",),
        )
    with pytest.raises(ValueError, match="at least one evidence URL"):
        AdjudicationRecord("case", "safety", ("r1", "r2"), 3, "editor", "reason")
    with pytest.raises(ValueError, match="absolute http"):
        AdjudicationRecord(
            "case",
            "safety",
            ("r1", "r2"),
            3,
            "editor",
            "reason",
            ("ftp://example.org/evidence",),
        )

    citations_path = tmp_path / "citations.yaml"
    citations_path.write_text(
        "citations:\n  - id: c\n    title: C\n    authors: [A]\n    year: 2026\n    kind: paper\n    url: https://example.org/c\n",
        encoding="utf-8",
    )
    claims_path = tmp_path / "claims.yaml"
    claims_path.write_text(
        "claims:\n  - id: x\n    text: X\n    evidence_tier: source\n    status: supported\n    citation_ids: [c]\n",
        encoding="utf-8",
    )
    assert load_citations(citations_path)[0].citation_id == "c"
    assert load_claims(claims_path)[0].claim_id == "x"

    adjudication = AdjudicationRecord(
        "case",
        "safety",
        ("r1", "r2"),
        3,
        "editor",
        "Both raters cited the source boundary.",
        ("https://example.org/evidence",),
    )
    assert AdjudicationRecord.from_mapping(adjudication.to_dict()) == adjudication
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3),
    )
    assert validate_adjudications((adjudication,), ratings)["ok"]
    with pytest.raises(ValueError, match="two distinct"):
        AdjudicationRecord("case", "safety", ("r1",), 3, "editor", "reason")

    adjudication_path = tmp_path / "adjudication.json"
    adjudication_path.write_text(
        json.dumps({"adjudications": [adjudication.to_dict()]}), encoding="utf-8"
    )
    assert load_adjudications(adjudication_path) == (adjudication,)
    bibliography = load_bibliography_keys(_checkout_manuscript_dir() / "references.bib")
    manuscript_citations = extract_manuscript_citations(_checkout_manuscript_dir())
    assert validate_bibliography(
        load_citations(Path("data/citations.yaml")), bibliography, manuscript_citations
    )["ok"]


def _fixture_observation(**overrides: object) -> EvaluationObservation:
    fields: dict[str, object] = dict(
        observation_id="obs",
        case_id="case",
        source="unknown",
        profile_id="fixture",
        target_id="page",
        run_id="run",
        observed_at="2026-01-01T00:00:00+00:00",
        page_count=1,
        request_count=1,
        accepted_pages=1,
        rejected_requests=0,
        redirect_count=0,
        canonical_count=0,
        duplicate_count=0,
        truncated_pages=0,
        response_bytes=100,
        cache_hits=0,
        provider_attempts=1,
        provider_failures=0,
        retry_count=0,
        fallback_used=False,
        selected_backend="deterministic",
        generator="deterministic",
        generation_duration_ms=1,
        artifact_sha256="a" * 64,
        skill_sha256="b" * 64,
        package_valid=True,
        provenance_complete=True,
        required_sections_valid=True,
        unsafe_source_preserved=False,
    )
    fields.update(overrides)
    return EvaluationObservation(**fields)


def test_evaluation_observation_rejects_invalid_fields() -> None:
    assert _fixture_observation().page_count == 1
    with pytest.raises(ValueError, match="page_count must be non-negative"):
        _fixture_observation(page_count=-1)
    with pytest.raises(
        ValueError, match="source coverage cannot exceed source page total"
    ):
        _fixture_observation(source_coverage_pages=2, source_page_total=1)
    with pytest.raises(ValueError, match="artifact and skill hashes are required"):
        _fixture_observation(artifact_sha256="")
    with pytest.raises(ValueError, match="artifact and skill hashes are required"):
        _fixture_observation(skill_sha256="")
    with pytest.raises(ValueError, match="observation source must be"):
        _fixture_observation(source="Live")
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(package_valid=1)
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(fallback_used=2)
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(provenance_complete="yes")


def test_statistics_are_bounded_and_reproducible() -> None:
    assert exact_binomial_interval(0, 0) is None
    assert exact_binomial_interval(0, 10)[0] == 0.0
    assert exact_binomial_interval(10, 10)[1] == 1.0
    assert exact_binomial_interval(5, 10)[0] < 0.5 < exact_binomial_interval(5, 10)[1]
    assert bootstrap_interval([1.0, 2.0]) is None
    values = [float(index) for index in range(20)]
    assert bootstrap_interval(values, seed=7) == bootstrap_interval(values, seed=7)
    assert numeric_summary([])["missing"]
    assert numeric_summary(values)["n"] == 20
    assert numeric_summary(values)["quartiles"] == {"q1": 4.75, "q3": 14.25}
    assert weighted_cohen_kappa({"a": 1, "b": 2}, {"a": 1, "b": 2}) == 1.0
    assert weighted_cohen_kappa({}, {}) is None
    assert exact_binomial_interval(2, 1) is None
    assert exact_binomial_interval(1, 1, confidence=1.0) is None
    assert not _is_iso_timestamp("not-a-timestamp")


def test_review_summary_gates_and_reports_agreement() -> None:
    rating = ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3)
    assert review_summary((rating,))["status"] == "pending"
    second = ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3)
    summary = review_summary((rating, second))
    assert summary["status"] == "complete"
    assert summary["paired_case_count"] == 1
    assert "semantic_coverage" in summary["agreement"]
    disjoint = review_summary((rating, ReviewRating("other", "r2", 4, 2, 2, 4, 3, 3)))
    assert disjoint["status"] == "pending"
    assert disjoint["agreement_status"] == "pending"
    assert disjoint["paired_case_count"] == 0
    with pytest.raises(ValueError, match="0 to 4"):
        ReviewRating("case", "r1", 5, 3, 2, 4, 4, 3)
    with pytest.raises(ValueError, match="evidence_urls"):
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3, evidence_urls=("relative",))


def test_run_snapshot_carries_complete_reference_payload(
    fixture_server: str, tmp_path: Path
) -> None:
    """The 05_render snapshot copies the whole package payload byte-exactly.

    Regression: the snapshot writer used to record only SKILL.md and a
    re-serialized manifest.json, so research observations validated against
    the snapshot silently lost the references/sources.json provenance and
    regeneration manifest that render_skill writes into the package.
    """
    profile = SourceProfile(
        id="fixture-snapshot",
        name="Fixture Snapshot Site",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Snapshot-Page", urls=("/page",)),),
    )
    output = tmp_path / "output"
    run_profile(profile, output_dir=output)
    run_manifest_path = next((output / "runs").glob("*/manifest.json"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    target_record = run_manifest["target_records"][0]
    snapshot = output / target_record["package_snapshot"]
    canonical = output / "skills" / "Snapshot-Page"
    expected_files = {
        "SKILL.md",
        "manifest.json",
        "regeneration.json",
        "references/sources.json",
    }
    snapshot_files = {
        str(path.relative_to(snapshot.parent))
        for path in snapshot.parent.rglob("*")
        if path.is_file()
    }
    assert snapshot_files == expected_files
    for relative in sorted(expected_files):
        assert (snapshot.parent / relative).read_bytes() == (
            canonical / relative
        ).read_bytes(), relative
    from skillarum.render import validate_skill_package

    validate_skill_package(snapshot, enforce_path_authority=False)


def test_evaluation_aggregation_figures_and_manuscript(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = SourceProfile(
        id="fixture-research",
        name="Fixture Research Site",
        base_url=fixture_server,
        crawl=CrawlConfig(respect_robots=False, allow_private_hosts=True),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="page", name="Research-Page", urls=("/page",)),),
    )
    output = tmp_path / "output"
    run_profile(profile, output_dir=output)
    observations = collect_observations(output, source="fixture")
    assert len(observations) == 1
    assert observations[0].package_valid
    assert observations[0].provenance_complete
    assert observations[0].source_coverage_pages == 1
    assert observations[0].source_page_total == 1
    run_manifest_path = next((output / "runs").glob("*/manifest.json"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    target_record = run_manifest["target_records"][0]
    snapshot = output / target_record["package_snapshot"]
    snapshot_manifest = snapshot.parent / "manifest.json"
    snapshot_payload = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
    assert _run_provenance_matches(run_manifest_path, target_record, snapshot_payload)
    assert (
        _run_provenance_matches(run_manifest_path, target_record, {"schema_version": 1})
        is None
    )
    profile_mismatch = dict(snapshot_payload)
    profile_mismatch["profile_id"] = "wrong"
    assert not _run_provenance_matches(
        run_manifest_path, target_record, profile_mismatch
    )
    url_mismatch = dict(snapshot_payload)
    url_mismatch["source_urls"] = []
    assert not _run_provenance_matches(run_manifest_path, target_record, url_mismatch)
    page_count_mismatch = dict(snapshot_payload)
    page_count_mismatch["pages"] = []
    assert not _run_provenance_matches(
        run_manifest_path, target_record, page_count_mismatch
    )
    non_object_page = dict(snapshot_payload)
    non_object_page["pages"] = ["not-an-object"]
    assert not _run_provenance_matches(
        run_manifest_path, target_record, non_object_page
    )
    snapshot_payload["pages"][0]["text_sha256"] = "0" * 64
    snapshot_manifest.write_text(json.dumps(snapshot_payload), encoding="utf-8")
    lineage_observation = collect_observations(output, source="fixture")[0]
    assert lineage_observation.package_valid
    assert not lineage_observation.provenance_complete
    assert lineage_observation.metadata["run_provenance_match"] is False
    prepared_path = run_manifest_path.parent / "02_prepare" / "page.json"
    prepared_payload = prepared_path.read_text(encoding="utf-8")
    prepared_path.unlink()
    missing_lineage = collect_observations(output, source="fixture")[0]
    assert missing_lineage.metadata["run_provenance_match"] is False
    prepared_path.write_text(prepared_payload, encoding="utf-8")
    valid_snapshot_text = snapshot_manifest.read_text(encoding="utf-8")
    snapshot_manifest.write_text("{not valid json", encoding="utf-8")
    corrupted_observation = collect_observations(output, source="fixture")[0]
    assert not corrupted_observation.package_valid
    assert "JSONDecodeError" in corrupted_observation.metadata["manifest_read_error"]
    assert not corrupted_observation.metadata["artifact_hash_available"]
    snapshot_manifest.write_text(valid_snapshot_text, encoding="utf-8")
    duplicate_run = output / "runs" / "conflicting-copy"
    shutil.copytree(run_manifest_path.parent, duplicate_run)
    duplicate_manifest_path = duplicate_run / "manifest.json"
    duplicate_manifest = json.loads(duplicate_manifest_path.read_text(encoding="utf-8"))
    duplicate_manifest["target_records"][0]["skill_sha256"] = "0" * 64
    duplicate_manifest_path.write_text(json.dumps(duplicate_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting evaluation observations"):
        collect_observations(output, source="fixture")
    summary = summarize_observations(observations)
    assert summary["observation_count"] == 1
    assert summary["area_count"] == 1
    assert summary["areas"]["fixture-research"]["accepted_pages"] == 1
    assert summary["source_coverage"]["rate"] == 1.0
    assert summary["proportions"]["package_valid"]["exact_95_interval"][1] == 1.0
    report = build_evaluation_report(observations)
    assert build_evaluation_report(observations).report_id == report.report_id
    report_path = write_evaluation_report(report, output)
    report_manifest = json.loads(
        (output / "reports/evaluation-manifest.json").read_text(encoding="utf-8")
    )
    assert report_manifest["report_sha256"]
    tampered_report = tmp_path / "tampered-report.json"
    tampered_payload = json.loads(report_path.read_text(encoding="utf-8"))
    tampered_payload["summary"]["observation_count"] = 999
    tampered_report.write_text(json.dumps(tampered_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash"):
        load_evaluation_report(tampered_report)
    restored = load_evaluation_report(report_path)
    assert restored.report_id == report.report_id

    registry = generate_figures(restored, output / "figures", source_data=report_path)
    validation = validate_figure_registry(registry)
    assert validation["ok"]
    assert validation["figure_count"] == 11
    registry_payload = json.loads(registry.read_text(encoding="utf-8"))
    assert registry_payload["schema_version"] == 4
    area_figure = next(
        item
        for item in registry_payload["figures"]
        if item["figure_id"] == "area-catalog"
    )
    assert area_figure["units"]
    assert area_figure["aggregation"]
    assert "does not establish" in area_figure["caption"]
    assert area_figure["alt_text"]
    assert area_figure["evidence_origin"] == "fixture=1"
    assert {item["figure_id"] for item in registry_payload["figures"]} >= {
        "coverage-truncation",
        "request-pressure",
    }
    expanded = replace(restored, observations=restored.observations * 6)
    expanded_report_path = write_evaluation_report(
        expanded, tmp_path / "expanded-output"
    )
    expanded_registry = generate_figures(
        expanded,
        tmp_path / "expanded-figures",
        source_data=expanded_report_path,
    )
    assert validate_figure_registry(expanded_registry)["ok"]
    rated = build_evaluation_report(
        restored.observations,
        ratings=(
            ReviewRating(
                "page",
                "rater-1",
                3,
                3,
                4,
                4,
                4,
                3,
                notes="evidence",
                evidence_urls=(fixture_server + "/page",),
            ),
            ReviewRating(
                "page",
                "rater-2",
                4,
                3,
                3,
                4,
                4,
                4,
                notes="evidence",
                evidence_urls=(fixture_server + "/page",),
            ),
        ),
    )
    rated_report_path = write_evaluation_report(rated, tmp_path / "rated-output")
    rated_registry = generate_figures(
        rated, tmp_path / "rated-figures", source_data=rated_report_path
    )
    rated_validation = validate_figure_registry(rated_registry)
    assert rated_validation["ok"]
    assert rated_validation["figure_count"] == 12
    review_figure = next(
        item
        for item in json.loads(rated_registry.read_text(encoding="utf-8"))["figures"]
        if item["figure_id"] == "human-review-rubric"
    )
    assert review_figure["sample_size"] == 2
    assert review_figure["evidence_origin"].startswith("two-rater review")
    first_entry = registry_payload["figures"][0]
    # The canonical artifact may be binary (PNG) or text (SVG); tamper with the
    # text vector companion when present, else the canonical artifact itself.
    text_artifact = first_entry.get("vector_path") or first_entry["path"]
    first_figure = registry.parent / text_artifact
    original_figure = first_figure.read_text(encoding="utf-8")
    first_figure.write_text(original_figure + "tampered", encoding="utf-8")
    assert not validate_figure_registry(registry)["ok"]
    first_figure.write_text(original_figure, encoding="utf-8")
    assert all(
        (registry.parent / item["path"]).exists()
        for item in json.loads(registry.read_text())["figures"]
    )
    publication_manifest = write_publication_manifest(output)
    assert validate_publication_manifest(publication_manifest)["ok"]
    publication_with_metadata = write_publication_manifest(
        output, project_root=Path.cwd()
    )
    metadata_payload = json.loads(publication_with_metadata.read_text(encoding="utf-8"))
    assert "manuscript/skillarum_cover.png" in metadata_payload["artifact_hashes"]
    assert "manuscript/provenance/CITATION.cff" in metadata_payload["artifact_hashes"]
    publication_payload = json.loads(publication_manifest.read_text(encoding="utf-8"))
    assert "manuscript/AGENTS.md" not in publication_payload["artifact_hashes"]
    assert "manuscript/README.md" not in publication_payload["artifact_hashes"]
    assert (
        sum(
            path.startswith("evaluation/")
            for path in publication_payload["artifact_hashes"]
        )
        == 1
    )
    (output / "evaluation" / "stale.json").write_text("{}", encoding="utf-8")
    refreshed_publication = write_publication_manifest(output)
    refreshed_payload = json.loads(refreshed_publication.read_text(encoding="utf-8"))
    assert "evaluation/stale.json" not in refreshed_payload["artifact_hashes"]
    secret_path = output / "web" / "secret.html"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_text("OPENAI_API_KEY=should-not-publish", encoding="utf-8")
    with pytest.raises(ValueError, match="credential marker"):
        write_publication_manifest(output)
    secret_path.unlink()
    publication_payload = json.loads(publication_manifest.read_text(encoding="utf-8"))
    publication_payload["artifact_hashes"]["skills/index.json"] = "tampered"
    tampered_publication = tmp_path / "publication-manifest.json"
    tampered_publication.write_text(json.dumps(publication_payload), encoding="utf-8")
    assert not validate_publication_manifest(tampered_publication)["ok"]

    manuscript = tmp_path / "manuscript"
    manuscript.mkdir()
    (manuscript / "00.md").write_text(
        "# Report\n\nObservations: {{OBSERVATION_COUNT}}\n\n"
        "![Figure](../output/figures/pipeline-trust-boundaries.png)\n",
        encoding="utf-8",
    )
    assert validate_manuscript_tree(manuscript, figure_registry=registry)["ok"]
    rendered = render_manuscript(manuscript, output / "manuscript", restored)
    assert "{{" not in rendered[0].read_text(encoding="utf-8")
    assert manuscript_variables(restored)["OBSERVATION_COUNT"] == "1"


def test_cli_research_commands_and_tamper_detection(
    fixture_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"id: fixture-cli\nname: Fixture CLI\nbase_url: {fixture_server}\n"
        "crawl:\n  respect_robots: false\n  allow_private_hosts: true\n"
        "targets:\n  - id: page\n    name: Page\n    urls: [/page]\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    assert (
        main(
            [
                "evaluate",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    report_path = Path(report["report"])
    assert report["ok"]
    assert report["summary"]["source_types"]["fixture"] == 1
    header = "case_id,rater_id,semantic_coverage,procedural_usefulness,verification_quality,provenance_fidelity,safety,readability,notes,evidence_urls\n"
    row = "page,{rater},4,3,3,4,4,3,evidence note,\n"
    rater_one = tmp_path / "rater-one.csv"
    rater_two = tmp_path / "rater-two.csv"
    rater_one.write_text(header + row.format(rater="r1"), encoding="utf-8")
    rater_two.write_text(header + row.format(rater="r2"), encoding="utf-8")
    assert (
        main(
            [
                "evaluate",
                "--output-dir",
                str(output),
                "--ratings",
                str(rater_one),
                "--ratings",
                str(rater_two),
                "--json",
            ]
        )
        == 0
    )
    rated_report = json.loads(capsys.readouterr().out)
    assert rated_report["rating_status"] == "complete"
    assert rated_report["summary"]["review"]["paired_case_count"] == 1
    assert (
        main(
            [
                "figures",
                "--evaluation",
                str(report_path),
                "--output-dir",
                str(output / "figures"),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["validation"]["ok"]

    citations = tmp_path / "citations.yaml"
    citations.write_text(
        "citations:\n  - id: c\n    title: C\n    authors: [A]\n    year: 2026\n    kind: paper\n    url: https://example.org/c\n",
        encoding="utf-8",
    )
    claims = tmp_path / "claims.yaml"
    claims.write_text(
        "claims:\n  - id: x\n    text: X\n    evidence_tier: source\n    status: supported\n    citation_ids: [c]\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "research",
                "validate",
                "--citations",
                str(citations),
                "--claims",
                str(claims),
                "--figures",
                str(output / "figures/figure_registry.json"),
                "--publication",
                str(tmp_path / "missing-publication-manifest.json"),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["ok"]
    # Deliberately omits --citations/--claims/--manuscript-dir so
    # bibliography_validation exercises this checkout's real manuscript and
    # references.bib (cli.py only runs that check when --citations is the
    # literal "data/citations.yaml" default). Both generated-artifact inputs
    # stay under tmp_path; local publication renders must not affect this test.
    assert (
        main(
            [
                "research",
                "validate",
                "--figures",
                str(output / "figures/figure_registry.json"),
                "--publication",
                str(tmp_path / "still-missing-publication-manifest.json"),
                "--evaluation",
                str(report_path),
                "--json",
            ]
        )
        == 0
    )
    default_validation = json.loads(capsys.readouterr().out)
    assert default_validation["bibliography_validation"]["ok"]
    assert main(["research", "publication", "--output-dir", str(output), "--json"]) == 0
    publication_result = json.loads(capsys.readouterr().out)
    assert publication_result["validation"]["ok"]
    assert main(["research", "publication", "--output-dir", str(output)]) == 0
    capsys.readouterr()
    ratings_template = tmp_path / "ratings.csv"
    assert (
        main(
            [
                "research",
                "ratings-template",
                "--output",
                str(ratings_template),
                "--case",
                "page",
                "--json",
            ]
        )
        == 0
    )
    assert "semantic_coverage" in ratings_template.read_text(encoding="utf-8")
    assert load_ratings(ratings_template) == ()
    capsys.readouterr()

    registry_path = output / "figures/figure_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["figures"][0]["caption"] = ""
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    assert (
        main(
            [
                "research",
                "validate",
                "--citations",
                str(citations),
                "--claims",
                str(claims),
                "--figures",
                str(registry_path),
                "--json",
            ]
        )
        == 1
    )
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_research_edge_validation_and_cli_text_paths(
    fixture_server: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = EvaluationCase("case", "Case", "profile", "target", repetitions=2)
    assert EvaluationCase.from_mapping(case.to_dict()) == case
    with pytest.raises(ValueError, match="positive"):
        EvaluationCase("case", "Case", "profile", "target", repetitions=0)
    with pytest.raises(ValueError, match="non-empty"):
        EvaluationCase("", "Case", "profile", "target")

    duplicate_citations = tmp_path / "duplicate.yaml"
    duplicate_citations.write_text(
        "- id: c\n  title: C\n  kind: paper\n  url: https://example.org/c\n"
        "- id: c\n  title: C2\n  kind: paper\n  url: https://example.org/c2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_citations(duplicate_citations)
    ledger = validate_ledgers(
        (),
        (ClaimRecord("c", "claim", "source", "supported", citation_ids=("missing",)),),
    )
    assert not ledger["ok"] and "missing citations" in ledger["errors"][0]
    unknown_manuscript = tmp_path / "unknown-manuscript"
    unknown_manuscript.mkdir()
    (unknown_manuscript / "x.md").write_text("{{UNKNOWN_TOKEN}}", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown manuscript"):
        render_manuscript(
            unknown_manuscript, tmp_path / "rendered", build_evaluation_report(())
        )
    empty_validation = validate_manuscript_tree(tmp_path / "not-a-manuscript")
    assert not empty_validation["ok"]

    profile_path = tmp_path / "local.yaml"
    profile_path.write_text(
        f"id: local\nname: Local\nbase_url: {fixture_server}\n"
        "crawl:\n  respect_robots: false\n  allow_private_hosts: true\n"
        "targets:\n  - id: page\n    name: Page\n    urls: [/page]\n",
        encoding="utf-8",
    )
    output = tmp_path / "out"
    assert (
        main(["evaluate", "--profile", str(profile_path), "--output-dir", str(output)])
        == 0
    )
    capsys.readouterr()
    report_path = output / "reports/evaluation-summary.json"
    assert (
        main(
            [
                "figures",
                "--evaluation",
                str(report_path),
                "--output-dir",
                str(output / "figures"),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "research",
                "manuscript",
                "--evaluation",
                str(report_path),
                "--source-dir",
                str(_checkout_manuscript_dir()),
                "--output-dir",
                str(tmp_path / "manuscript-out"),
                "--figures",
                str(output / "figures/figure_registry.json"),
            ]
        )
        == 0
    )
    capsys.readouterr()
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:1")
    assert (
        main(["doctor", "--output-dir", str(tmp_path / "doctor"), "--no-network"]) == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "doctor",
                "--output-dir",
                str(tmp_path / "doctor2"),
                "--ollama-url",
                "http://user:pass@127.0.0.1:1",
                "--json",
            ]
        )
        == 1
    )
    capsys.readouterr()
    public_profile = tmp_path / "public.yaml"
    public_profile.write_text(
        profile_path.read_text().replace(fixture_server, "https://example.org"),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "evaluate",
                "--profile",
                str(public_profile),
                "--output-dir",
                str(tmp_path / "public"),
            ]
        )
        == 1
    )
    capsys.readouterr()
    assert main(["validate", str(tmp_path / "missing-SKILL.md")]) == 1
    capsys.readouterr()


def test_figure_registry_rejects_malformed_entries(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        validate_figure_registry(path)
    path.write_text(
        json.dumps({"schema_version": 1, "figures": "bad"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="list"):
        validate_figure_registry(path)
    path.write_text(
        json.dumps({"schema_version": 1, "figures": ["bad"]}), encoding="utf-8"
    )
    result = validate_figure_registry(path)
    assert not result["ok"]


def test_publication_and_package_validators_reject_symlinks(tmp_path: Path) -> None:
    from skillarum.render import validate_skill_package

    output = tmp_path / "output"
    package = output / "skills" / "Math4Wisdom" / "Three-Minds"
    package.mkdir(parents=True)
    source_package = render_skill(
        DeterministicGenerator().generate(_fixture_corpus("Three-Minds")),
        _fixture_corpus("Three-Minds"),
        tmp_path / "source-skills",
    ).parent
    (package / "SKILL.md").symlink_to(source_package / "SKILL.md")
    (package / "manifest.json").symlink_to(source_package / "manifest.json")
    with pytest.raises(ValueError, match="regular file"):
        validate_skill_package(package / "SKILL.md")

    (output / "reports").mkdir(parents=True)
    (output / "web").mkdir()
    source_web = tmp_path / "source-web.html"
    source_web.write_text("<html><body>fixture</body></html>", encoding="utf-8")
    (output / "web" / "index.html").symlink_to(source_web)
    with pytest.raises(ValueError, match="symlink"):
        write_publication_manifest(output)

    figures = tmp_path / "figures"
    figures.mkdir()
    empty_report = build_evaluation_report(())
    source_report = write_evaluation_report(empty_report, tmp_path / "source-output")
    source_figures = tmp_path / "source-output" / "figures"
    generate_figures(empty_report, source_figures, source_data=source_report)
    for filename in ("figure_registry.json", "figure_registry.manifest.json"):
        (figures / filename).write_bytes((source_figures / filename).read_bytes())
    for filename in ("pipeline-trust-boundaries.svg", "pipeline-trust-boundaries.png"):
        (figures / filename).symlink_to(source_figures / filename)
    for filename in (
        "run-state-machine.svg",
        "run-state-machine.png",
        "cache-integrity-flow.svg",
        "cache-integrity-flow.png",
        "acquisition-funnel.svg",
        "acquisition-funnel.png",
        "provider-fallback-outcomes.svg",
        "provider-fallback-outcomes.png",
        "generation-latency.svg",
        "generation-latency.png",
        "provenance-completeness.svg",
        "provenance-completeness.png",
        "area-catalog.svg",
        "area-catalog.png",
    ):
        (figures / filename).write_bytes((source_figures / filename).read_bytes())
    assert not validate_figure_registry(figures / "figure_registry.json")["ok"]


def test_publication_selection_and_figure_paths_are_integrity_bounded(
    tmp_path: Path,
) -> None:
    from skillarum.research import _resolve_output_reference

    empty_report = build_evaluation_report(())
    output = tmp_path / "output"
    report_path = write_evaluation_report(empty_report, output)
    manifest_path = output / "reports/evaluation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["report_file"] = f"output/evaluation/{report_path.name}"
    manifest["summary_file"] = "output/reports/evaluation-summary.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _resolve_output_reference(
        Path("output"), "output/evaluation/report.json"
    ) == Path("output/evaluation/report.json")
    publication = write_publication_manifest(output)
    assert validate_publication_manifest(publication)["ok"]
    canonical_report_file = manifest["report_file"]
    canonical_report_hash = manifest["report_sha256"]
    manifest["report_file"] = "output/reports/evaluation-summary.json"
    manifest["report_sha256"] = manifest["summary_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical evaluation report"):
        write_publication_manifest(output)
    manifest["report_file"] = canonical_report_file
    manifest["report_sha256"] = canonical_report_hash
    manifest["report_sha256"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="report hash"):
        write_publication_manifest(output)

    manifest = json.loads(
        (output / "reports/evaluation-manifest.json").read_text(encoding="utf-8")
    )
    manifest["schema_version"] = 999
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported evaluation manifest"):
        write_publication_manifest(output)
    manifest["schema_version"] = 1
    manifest.pop("report_file")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical report references"):
        write_publication_manifest(output)
    manifest = json.loads(
        (output / "reports/evaluation-manifest.json").read_text(encoding="utf-8")
    )
    manifest["report_file"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="outside output"):
        write_publication_manifest(output)
    manifest["report_file"] = str(report_path)
    manifest["report_sha256"] = (
        __import__("hashlib").sha256(report_path.read_bytes()).hexdigest()
    )
    manifest["summary_sha256"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="summary hash"):
        write_publication_manifest(output)
    manifest["summary_sha256"] = (
        __import__("hashlib")
        .sha256((output / "reports/evaluation-summary.json").read_bytes())
        .hexdigest()
    )
    manifest["report_id"] = "wrong-report-id"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="report_id"):
        write_publication_manifest(output)

    registry = generate_figures(
        empty_report, output / "figures", source_data=report_path
    )
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload["figures"][0]["path"] = str(
        (registry.parent / payload["figures"][0]["path"]).resolve()
    )
    payload["figures"][0]["raster_path"] = "../escape.png"
    registry.write_text(json.dumps(payload), encoding="utf-8")
    validation = validate_figure_registry(registry)
    assert not validation["ok"]
    assert any("must remain relative" in error for error in validation["errors"])


def test_manuscript_render_excludes_and_cleans_guidance_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "AGENTS.md").write_text("agent-only guidance", encoding="utf-8")
    (source / "README.md").write_text("local readme", encoding="utf-8")
    (source / "01_report.md").write_text(
        "# Report {{OBSERVATION_COUNT}}", encoding="utf-8"
    )
    (destination / "AGENTS.md").write_text("stale guidance", encoding="utf-8")
    (destination / "README.md").write_text("stale readme", encoding="utf-8")
    report = build_evaluation_report(())
    rendered = render_manuscript(source, destination, report)
    assert [path.name for path in rendered] == ["01_report.md"]
    assert not (destination / "AGENTS.md").exists()
    assert not (destination / "README.md").exists()
    assert validate_manuscript_tree(source)["file_count"] == 1


def test_load_cases_and_evaluate_case_attribution(
    fixture_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The declarative live-matrix plan binds stable case ids to observations."""
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        "schema_version: 1\ncases:\n"
        "  - id: declared-fixture-case\n    label: Declared case\n"
        "    profile_id: cp\n    target_id: page\n    source: live\n",
        encoding="utf-8",
    )
    loaded = load_cases(cases_path)
    assert loaded[0].case_id == "declared-fixture-case"
    assert loaded[0].profile_id == "cp"
    assert loaded[0].target_id == "page"
    assert loaded[0].source == "live"
    assert load_cases(cases_path) == loaded

    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "cases:\n"
        "  - id: x\n    label: X\n    profile_id: a\n    target_id: b\n"
        "  - id: x\n    label: X\n    profile_id: a\n    target_id: b\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_cases(dup)

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"id: cp\nname: CP\nbase_url: {fixture_server}\n"
        "crawl:\n  respect_robots: false\n  allow_private_hosts: true\n"
        "targets:\n  - id: page\n    name: Page\n    urls: [/page]\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    assert (
        main(
            [
                "evaluate",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(output),
                "--cases",
                str(cases_path),
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    report = load_evaluation_report(Path(result["report"]))
    assert report.observations[0].case_id == "declared-fixture-case"
    assert report.observations[0].source == "fixture"


def test_cli_evaluate_profile_forwards_command_generator(
    fixture_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Provider options given to evaluate --profile reach the generator run."""
    script = tmp_path / "generator.py"
    script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "print(json.dumps({'name': payload['skill_name'], 'description': 'External', "
        "'body': '# External\\n\\n## Source boundaries\\n\\nExternal source.\\n\\n"
        "## Semantic knowledge\\n\\nExternal semantics.\\n\\n"
        "## Procedural guidance\\n\\nExternal procedure.\\n\\n"
        "## Verification\\n\\nExternal verification.'}))\n",
        encoding="utf-8",
    )
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        f"id: cmd\nname: CMD\nbase_url: {fixture_server}\n"
        "crawl:\n  respect_robots: false\n  allow_private_hosts: true\n"
        "targets:\n  - id: page\n    name: Page\n    urls: [/page]\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    assert (
        main(
            [
                "evaluate",
                "--profile",
                str(profile_path),
                "--output-dir",
                str(output),
                "--backend",
                "command",
                "--generator-command",
                sys.executable,
                str(script),
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    report = load_evaluation_report(Path(result["report"]))
    observation = report.observations[0]
    assert observation.generator == "command"
    assert observation.selected_backend == "command"
    assert observation.package_valid


def test_ledger_loaders_reject_malformed_and_duplicate_entries(tmp_path: Path) -> None:
    bad_list = tmp_path / "bad-list.yaml"
    bad_list.write_text("citations: nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a list"):
        load_citations(bad_list)
    bad_map = tmp_path / "bad-map.yaml"
    bad_map.write_text("citations:\n  - nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="all be mappings"):
        load_citations(bad_map)
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "citations:\n"
        "  - id: c\n    title: T\n    authors: [A]\n    kind: paper\n    url: https://example.org\n"
        "  - id: c\n    title: T\n    authors: [A]\n    kind: paper\n    url: https://example.org\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_citations(dup)

    claims_bad_list = tmp_path / "cl.yaml"
    claims_bad_list.write_text("claims: nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a list"):
        load_claims(claims_bad_list)

    cases_bad = tmp_path / "cases-bad.yaml"
    cases_bad.write_text("cases: nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a list"):
        load_cases(cases_bad)
    cases_bad2 = tmp_path / "cases-bad2.yaml"
    cases_bad2.write_text("cases:\n  - nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must all be mappings"):
        load_cases(cases_bad2)

    adj_bad_list = tmp_path / "adj-list.json"
    adj_bad_list.write_text('{"adjudications": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a list"):
        load_adjudications(adj_bad_list)
    adj_bad_map = tmp_path / "adj-map.json"
    adj_bad_map.write_text('{"adjudications": [1, 2]}', encoding="utf-8")
    with pytest.raises(ValueError, match="must all be mappings"):
        load_adjudications(adj_bad_map)
    adjudication = AdjudicationRecord(
        "case",
        "safety",
        ("r1", "r2"),
        3,
        "editor",
        "Both raters cited the source boundary.",
        ("https://example.org/evidence",),
    )
    adj_dup = tmp_path / "adj-dup.json"
    adj_dup.write_text(
        json.dumps(
            {
                "adjudications": [
                    adjudication.to_dict(),
                    {**adjudication.to_dict(), "rationale": "other"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_adjudications(adj_dup)

    no_evidence = tmp_path / "ratings.csv"
    no_evidence.write_text(
        "case_id,rater_id,semantic_coverage,procedural_usefulness,verification_quality,provenance_fidelity,safety,readability,notes,evidence_urls\n"
        "case,r1,3,3,3,3,3,3,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="evidence"):
        load_ratings(no_evidence)


def test_ledger_and_adjudication_integrity_gates(tmp_path: Path) -> None:
    unsupported = ClaimRecord(
        "fresh",
        "A claim with no evidence.",
        evidence_tier="measured",
        status="supported",
    )
    assert not validate_ledgers((), (unsupported,))["ok"]

    adjudication = AdjudicationRecord(
        "case",
        "safety",
        ("r1", "r2"),
        3,
        "editor",
        "reason",
        ("https://example.org/evidence",),
    )
    assert not validate_adjudications((adjudication,), ())["ok"]


def test_publication_manifest_rejects_boundary_and_integrity_violations(
    tmp_path: Path,
) -> None:
    from skillarum.research import PUBLICATION_SCHEMA_VERSION

    output = tmp_path / "output"
    skills = output / "skills"
    skills.mkdir(parents=True)
    (skills / "a.md").write_text("x", encoding="utf-8")
    reports = output / "reports"
    reports.mkdir()
    manifest_path = reports / "publication-manifest.json"

    def write(hashes: dict, **extra: object) -> None:
        payload = {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "artifact_count": len(hashes),
            "artifact_hashes": hashes,
        }
        payload.update(extra)
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    good = {"skills/a.md": sha256_text("x")}
    write(good)
    assert validate_publication_manifest(manifest_path)["ok"]

    write(good, schema_version=99)
    with pytest.raises(ValueError, match="unsupported publication schema"):
        validate_publication_manifest(manifest_path)

    write({"runs/secret.json": "0" * 64})
    assert not validate_publication_manifest(manifest_path)["ok"]

    write({"skills/missing.md": "0" * 64})
    assert not validate_publication_manifest(manifest_path)["ok"]

    real = output / "real.md"
    real.write_text("r", encoding="utf-8")
    link = skills / "link.md"
    link.symlink_to(real)
    write({"skills/link.md": sha256_text("r")})
    assert not validate_publication_manifest(manifest_path)["ok"]
    link.unlink()

    write({"skills/a.md": "0" * 64})
    assert not validate_publication_manifest(manifest_path)["ok"]

    write(good, artifact_count=99)
    assert not validate_publication_manifest(manifest_path)["ok"]

    write(good)
    assert not validate_publication_manifest(manifest_path, require_rendered=True)["ok"]


# --- methods-lane hardening (2026-09-08) -------------------------------------


def test_observation_source_is_a_closed_vocabulary() -> None:
    with pytest.raises(ValueError, match="observation source must be"):
        _fixture_observation(source="Live")
    with pytest.raises(ValueError, match="observation source must be"):
        _fixture_observation(source="experimental")
    assert _fixture_observation(source="fixture").source == "fixture"


def test_observation_flags_must_be_strict_booleans() -> None:
    # A truthy integer such as package_valid=2 would previously sum as two
    # successes over one observation and inflate the reported proportion.
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(package_valid=2)
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(fallback_used=1)
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(provenance_complete="yes")
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(required_sections_valid=0)
    with pytest.raises(ValueError, match="must be a boolean"):
        _fixture_observation(unsafe_source_preserved=None)


def test_evaluation_case_source_is_a_closed_vocabulary() -> None:
    with pytest.raises(ValueError, match="fixture, live, or unknown"):
        EvaluationCase("c", "C", "p", "t", source="public")
    assert EvaluationCase("c", "C", "p", "t", source="live").source == "live"


def test_private_path_blocklists_are_case_insensitive(tmp_path: Path) -> None:
    # Negative control for the case-variant bypass: on a case-insensitive
    # filesystem "data/Runs/x" resolves to the private "data/runs/x", which
    # must not be citable as claim evidence.
    runs = tmp_path / "data" / "runs"
    runs.mkdir(parents=True)
    (runs / "evidence.json").write_text("{}", encoding="utf-8")
    claim = ClaimRecord(
        "c1",
        "Private-path citation attempt.",
        evidence_tier="measured",
        status="supported",
        artifact_paths=("data/Runs/evidence.json", "data/.Cache/e.json"),
    )
    result = validate_ledgers((), (claim,), artifact_root=tmp_path)
    assert result["ok"] is False
    assert len(result["errors"]) == 2, result["errors"]


def test_publication_manifest_rejects_case_variant_private_paths(
    tmp_path: Path,
) -> None:
    from skillarum.research import PUBLICATION_SCHEMA_VERSION

    runs = tmp_path / "Runs"
    runs.mkdir()
    secret = runs / "secret.json"
    secret.write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "artifact_count": 1,
        "artifact_hashes": {"Runs/secret.json": sha256_bytes(secret.read_bytes())},
        "excluded": [],
    }
    manifest_path = tmp_path / "reports" / "publication-manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate_publication_manifest(manifest_path)
    assert result["ok"] is False
    assert any("forbidden publication path" in error for error in result["errors"])


def test_validate_adjudications_flags_agreement_restatements() -> None:
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3),
    )
    restated = AdjudicationRecord(
        "case",
        "semantic_coverage",
        ("r1", "r2"),
        4,
        "editor",
        "Both raters scored 4.",
        ("https://example.org/evidence",),
    )
    disputed = AdjudicationRecord(
        "case",
        "procedural_usefulness",
        ("r1", "r2"),
        3,
        "editor",
        "Raters split 3 and 2.",
        ("https://example.org/evidence",),
    )
    result = validate_adjudications((restated, disputed), ratings)
    assert result["ok"] is True
    assert result["adjudications_without_disagreement"] == ["case/semantic_coverage"]


def test_load_ratings_reports_row_and_field_on_malformed_cells(
    tmp_path: Path,
) -> None:
    header = (
        "case_id,rater_id,semantic_coverage,procedural_usefulness,"
        "verification_quality,provenance_fidelity,safety,readability,notes,"
        "evidence_urls\n"
    )
    good = "case,r1,3,3,3,3,3,3,checked,https://example.org/a\n"
    out_of_range = tmp_path / "out-of-range.csv"
    out_of_range.write_text(
        header + good + "case,r2,9,3,3,3,3,3,checked,\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"row 3 .*0 to 4"):
        load_ratings(out_of_range)
    not_an_integer = tmp_path / "not-an-integer.csv"
    not_an_integer.write_text(
        header + good + "case,r2,three,3,3,3,3,3,checked,\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"row 3 .*invalid literal"):
        load_ratings(not_an_integer)
    blank_template = tmp_path / "blank.csv"
    blank_template.write_text(header + "case,,,,,,,," + "\n", encoding="utf-8")
    assert load_ratings(blank_template) == ()


def test_rating_template_rejects_csv_unsafe_case_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        write_rating_template(tmp_path / "blank.csv", ["  "])
    with pytest.raises(ValueError, match="commas, quotes"):
        write_rating_template(tmp_path / "comma.csv", ["a,b"])
    with pytest.raises(ValueError, match="commas, quotes"):
        write_rating_template(tmp_path / "newline.csv", ["a\nb"])
    output = write_rating_template(tmp_path / "ok.csv", ["case-1", "case-2"])
    text = output.read_text(encoding="utf-8")
    assert text.count("\n") == 3
    assert load_ratings(output) == ()


def _diagnostic_observation(**overrides: object) -> EvaluationObservation:
    fields: dict[str, object] = dict(
        observation_id="obs",
        case_id="case",
        source="fixture",
        profile_id="profile",
        target_id="target",
        run_id="run-1",
        observed_at="2026-01-01T00:00:00+00:00",
        page_count=1,
        request_count=1,
        accepted_pages=1,
        rejected_requests=0,
        redirect_count=0,
        canonical_count=0,
        duplicate_count=0,
        truncated_pages=0,
        response_bytes=10,
        cache_hits=0,
        provider_attempts=1,
        provider_failures=0,
        retry_count=0,
        fallback_used=False,
        selected_backend=None,
        generator="deterministic",
        generation_duration_ms=1,
        artifact_sha256="a" * 64,
        skill_sha256="b" * 64,
        package_valid=True,
        provenance_complete=True,
        required_sections_valid=True,
        unsafe_source_preserved=False,
        metadata={"source_urls": ["https://example.org/1"]},
    )
    fields.update(overrides)
    return EvaluationObservation(**fields)


def test_summarize_observations_distinguishes_runs_targets_and_pages() -> None:
    observations = (
        _diagnostic_observation(observation_id="obs-1"),
        _diagnostic_observation(
            observation_id="obs-2",
            run_id="run-2",
            metadata={
                "source_urls": [
                    "https://example.org/1",
                    "https://example.org/2",
                ]
            },
        ),
        _diagnostic_observation(
            observation_id="obs-3",
            target_id="other",
            metadata={"missing_metrics": ["fallback_used"]},
        ),
    )
    summary = summarize_observations(observations)
    assert summary["observation_count"] == 3
    assert summary["target_count"] == 2
    assert summary["run_count"] == 2
    assert summary["targets_observed_multiple_times"] == 1
    assert summary["max_observations_per_target"] == 2
    assert summary["unique_source_url_count"] == 2
    assert summary["source_url_instance_count"] == 3
    assert summary["observations_with_complete_telemetry"] == 2


def test_summarize_observations_empty_diagnostics_are_zeroed() -> None:
    summary = summarize_observations(())
    assert summary["run_count"] == 0
    assert summary["targets_observed_multiple_times"] == 0
    assert summary["max_observations_per_target"] == 0
    assert summary["unique_source_url_count"] == 0
    assert summary["source_url_instance_count"] == 0
    assert summary["observations_with_complete_telemetry"] == 0


def test_older_current_format_report_without_additive_keys_loads(
    tmp_path: Path,
) -> None:
    report = build_evaluation_report((_fixture_observation(),))
    payload = report.to_dict()
    for key in sorted(ADDITIVE_SUMMARY_KEYS):
        payload["summary"].pop(key, None)
    payload.pop("artifact_sha256")
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "older-current-format.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_evaluation_report(path)
    for key in sorted(ADDITIVE_SUMMARY_KEYS):
        assert loaded.summary[key] == report.summary[key]
    expected_digest = sha256_json(
        {
            key: value
            for key, value in loaded.to_dict().items()
            if key != "artifact_sha256"
        }
    )
    assert loaded.artifact_sha256 == expected_digest


def test_evaluation_report_round_trip_preserves_payload_exactly(
    tmp_path: Path,
) -> None:
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3, notes="checked"),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3, notes="checked"),
    )
    report = build_evaluation_report((_fixture_observation(),), ratings=ratings)
    destination = write_evaluation_report(report, tmp_path)
    loaded = load_evaluation_report(destination)
    assert loaded.to_dict() == report.to_dict()
