"""Figure quality, provenance binding, and accessibility regressions.

These tests treat the figure writer as the real renderer it is: they build
real evaluation reports, run the real generator, and inspect the produced
SVG/JSON artifacts. No mock frameworks.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from skillarum.figures import (
    PALETTE,
    _bar_figure,
    _grouped_bar_figure,
    generate_figures,
    validate_figure_registry,
)
from skillarum.research import (
    EvaluationObservation,
    ReviewRating,
    build_evaluation_report,
    write_evaluation_report,
)


def _observation(**overrides: Any) -> EvaluationObservation:
    defaults: dict[str, Any] = dict(
        observation_id="obs-1",
        case_id="case-1",
        source="fixture",
        profile_id="fixture-research",
        target_id="page",
        run_id="run-1",
        observed_at="2026-01-01T00:00:00+00:00",
        page_count=2,
        request_count=3,
        accepted_pages=2,
        rejected_requests=1,
        redirect_count=0,
        canonical_count=0,
        duplicate_count=0,
        truncated_pages=0,
        response_bytes=1000,
        cache_hits=0,
        provider_attempts=1,
        provider_failures=0,
        retry_count=0,
        fallback_used=False,
        selected_backend="deterministic",
        generator="deterministic",
        generation_duration_ms=0,
        artifact_sha256="a" * 64,
        skill_sha256="b" * 64,
        package_valid=True,
        provenance_complete=True,
        required_sections_valid=True,
        unsafe_source_preserved=True,
        metadata={},
        source_coverage_pages=2,
        source_page_total=2,
        area="Fixture Area",
    )
    defaults.update(overrides)
    return EvaluationObservation(**defaults)


def _mixed_report() -> Any:
    return build_evaluation_report(
        (
            _observation(fallback_used=True),
            _observation(
                observation_id="obs-2",
                case_id="case-2",
                target_id="other",
                run_id="run-2",
                source_coverage_pages=1,
                source_page_total=3,
                truncated_pages=1,
                package_valid=False,
                provenance_complete=False,
            ),
            _observation(
                observation_id="obs-3",
                case_id="case-3",
                target_id="third",
                run_id="run-3",
                source_coverage_pages=0,
                source_page_total=0,
            ),
        )
    )


def _registry_for(tmp_path: Path, report: Any) -> tuple[Path, Path, dict[str, Any]]:
    """Generate figures and return (report_path, registry_path, payload)."""
    report_path = write_evaluation_report(report, tmp_path / "report-output")
    registry_path = generate_figures(
        report, tmp_path / "figures", source_data=report_path
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    return report_path, registry_path, payload


def test_proportion_intervals_match_report_denominators(tmp_path: Path) -> None:
    report = _mixed_report()
    _, registry_path, registry = _registry_for(tmp_path, report)
    from skillarum.research import _publication_artifact_paths

    assert (
        tmp_path / "figures/figure_data/proportion-intervals.json"
        in _publication_artifact_paths(tmp_path)
    )
    assert validate_figure_registry(registry_path)["ok"]
    assert registry["report_id"] == report.report_id
    entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    assert entry["report_id"] == report.report_id
    assert entry["denominator"].strip()
    assert entry["vector_path"]
    sidecar_path = registry_path.parent / entry["data_path"]
    assert hashlib.sha256(sidecar_path.read_bytes()).hexdigest() == entry["data_sha256"]
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["figure_id"] == "proportion-intervals"
    assert sidecar["report_id"] == report.report_id
    assert sidecar["source_sha256"] == entry["source_sha256"]
    summary_proportions = report.summary["proportions"]
    assert set(row["key"] for row in sidecar["rows"]) == set(summary_proportions)
    for row in sidecar["rows"]:
        record = summary_proportions[row["key"]]
        assert row["successes"] == record["successes"]
        assert row["total"] == record["total"]
        assert row["rate"] == record["rate"]
        interval = record["exact_95_interval"]
        assert row["exact_95_interval"] == (
            list(interval) if interval is not None else None
        )
    fallback_row = next(row for row in sidecar["rows"] if row["key"] == "fallback_used")
    assert fallback_row["total"] == 3
    coverage_row = next(
        row for row in sidecar["rows"] if row["key"] == "source_coverage"
    )
    assert coverage_row["successes"] == 3
    assert coverage_row["total"] == 5
    caption = entry["caption"]
    assert "n=" in caption
    assert "does not establish" in caption
    assert "independent Bernoulli" in caption
    assert "not calibrated" in caption
    assert "95%" in caption  # default policy confidence
    assert entry["alt_text"].strip().casefold() != caption.strip().casefold()
    assert len(entry["alt_text"]) >= 20


def test_proportion_intervals_empty_report_marks_missing_denominators(
    tmp_path: Path,
) -> None:
    report = build_evaluation_report(())
    _, registry_path, registry = _registry_for(tmp_path, report)
    validation = validate_figure_registry(registry_path)
    assert validation["ok"]
    assert validation["figure_count"] == 11
    entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    sidecar = json.loads(
        (registry_path.parent / entry["data_path"]).read_text(encoding="utf-8")
    )
    assert sidecar["rows"]
    assert all(row["total"] == 0 and row["percent"] is None for row in sidecar["rows"])
    vector = (registry_path.parent / entry["vector_path"]).read_text(encoding="utf-8")
    assert "no eligible denominator (n=0)" in vector


def test_registry_entries_carry_bindings_and_distinct_alt_text(tmp_path: Path) -> None:
    _, _, registry = _registry_for(tmp_path, _mixed_report())
    assert registry["schema_version"] == 4
    assert len(registry["figures"]) == 11
    for entry in registry["figures"]:
        assert entry["report_id"].strip()
        assert entry["denominator"].strip()
        alt = entry["alt_text"].strip().casefold()
        caption = entry["caption"].strip().casefold()
        assert alt and caption and alt != caption
        assert "n=" in entry["caption"]
        assert any(
            phrase in caption
            for phrase in ("does not establish", "not establish", "not a ", "not an ")
        )


def test_generation_is_byte_deterministic(tmp_path: Path) -> None:
    report = _mixed_report()
    report_path = write_evaluation_report(report, tmp_path / "report-source")
    digests = []
    for index in (1, 2):
        output_root = tmp_path / f"out-{index}"
        evaluation_dir = output_root / "evaluation"
        evaluation_dir.mkdir(parents=True)
        shutil.copyfile(report_path, evaluation_dir / report_path.name)
        registry_path = generate_figures(
            report,
            output_root / "figures",
            source_data=evaluation_dir / report_path.name,
        )
        root = registry_path.parent
        # Provenance references are generation-root-relative, so every
        # artifact, the manifest included, must be byte-identical across
        # identically laid-out generation roots.
        artifacts = sorted(path for path in root.rglob("*") if path.is_file())
        digests.append(
            {
                str(path.relative_to(root)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in artifacts
            }
        )
    assert digests[0] == digests[1]


def test_provenance_paths_stay_portable_and_rejections_fire(tmp_path: Path) -> None:
    report = _mixed_report()
    report_path = write_evaluation_report(report, tmp_path / "report-output")
    registry_path = generate_figures(
        report, tmp_path / "figures", source_data=report_path
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    manifest = json.loads(
        registry_path.with_name("figure_registry.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["registry_file"] == "figures/figure_registry.json"
    expected_source = report_path.relative_to(tmp_path).as_posix()
    for entry in payload["figures"]:
        assert entry["source_data"] == expected_source
        sidecar = entry.get("data_path")
        if sidecar:
            table = json.loads(
                (registry_path.parent / sidecar).read_text(encoding="utf-8")
            )
            assert table["source_data"] == expected_source
    assert validate_figure_registry(registry_path)["ok"]
    # An absolute provenance path is exactly the machine-specific leak the
    # portable-path contract forbids: the validator must reject it.
    payload["figures"][0]["source_data"] = str(report_path.resolve())
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    check = validate_figure_registry(registry_path)
    assert not check["ok"]
    assert any("portable" in error for error in check["errors"])
    payload["figures"][0]["source_data"] = "../" + expected_source
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    check = validate_figure_registry(registry_path)
    assert not check["ok"]
    assert any("portable" in error for error in check["errors"])


def test_generation_rejects_mismatched_source_report(tmp_path: Path) -> None:
    report_a = build_evaluation_report((_observation(),))
    report_b = build_evaluation_report(
        (_observation(observation_id="obs-2", case_id="case-2", target_id="other"),)
    )
    path_a = write_evaluation_report(report_a, tmp_path / "report-output")
    with pytest.raises(ValueError, match="report_id"):
        generate_figures(report_b, tmp_path / "figs", source_data=path_a)
    tampered = tmp_path / "tampered-report.json"
    payload = json.loads(path_a.read_text(encoding="utf-8"))
    payload["artifact_sha256"] = "f" * 64
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_sha256"):
        generate_figures(report_a, tmp_path / "figs-2", source_data=tampered)
    junk = tmp_path / "junk.json"
    junk.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not readable JSON"):
        generate_figures(report_a, tmp_path / "figs-3", source_data=junk)


def test_generation_rejects_altered_body_and_rehashed_report(tmp_path: Path) -> None:
    from skillarum.research import _report_payload_hash

    report = build_evaluation_report((_observation(),))
    path = write_evaluation_report(report, tmp_path / "report-output")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Altered body with the original digest string retained: the file is no
    # longer internally consistent and must be rejected before plotting.
    retained = dict(payload)
    retained["summary"] = {**payload["summary"], "observation_count": 999}
    altered_body = tmp_path / "altered-body.json"
    altered_body.write_text(json.dumps(retained), encoding="utf-8")
    with pytest.raises(ValueError, match="file contents"):
        generate_figures(report, tmp_path / "figs-1", source_data=altered_body)
    # Rehashed divergent report: internally consistent bytes that describe a
    # different report than the one passed in memory.
    rehashed = dict(payload)
    rehashed["summary"] = {**payload["summary"], "observation_count": 42}
    rehashed["artifact_sha256"] = _report_payload_hash(rehashed)
    divergent = tmp_path / "rehashed.json"
    divergent.write_text(json.dumps(rehashed), encoding="utf-8")
    with pytest.raises(ValueError, match="in-memory report"):
        generate_figures(report, tmp_path / "figs-2", source_data=divergent)


def test_validate_catches_stale_report_and_sidecar_binding(tmp_path: Path) -> None:
    report_path, registry_path, registry_payload = _registry_for(
        tmp_path, _mixed_report()
    )
    # A stale report file (report regenerated without regenerating figures)
    # must fail the registry's source-data hash check.
    original = report_path.read_bytes()
    report_path.write_bytes(original + b" ")
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("source data hash mismatch" in error for error in result["errors"])
    report_path.write_bytes(original)
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        item
        for item in registry_payload["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    sidecar_path = registry_path.parent / entry["data_path"]
    original_sidecar = sidecar_path.read_bytes()
    # Byte-level tampering fails the recorded data hash.
    sidecar_path.write_bytes(original_sidecar + b" ")
    assert any(
        "data file hash mismatch" in error
        for error in validate_figure_registry(registry_path)["errors"]
    )
    sidecar_path.write_bytes(original_sidecar)
    # A consistently re-hashed sidecar that binds a different report must fail
    # the cross-binding check, not just the byte hash.
    payload = json.loads(original_sidecar.decode("utf-8"))
    payload["source_sha256"] = "0" * 64
    sidecar_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    updated = dict(entry)
    updated["data_sha256"] = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()
    registry_payload["figures"] = [
        updated if item["figure_id"] == "proportion-intervals" else item
        for item in registry_payload["figures"]
    ]
    registry_path.write_text(json.dumps(registry_payload), encoding="utf-8")
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("data table source hash mismatch" in error for error in result["errors"])
    # A rehashed non-object sidecar must fail as a diagnostic, not crash the gate.
    sidecar_path.write_text("null")
    updated["data_sha256"] = hashlib.sha256(sidecar_path.read_bytes()).hexdigest()
    registry_path.write_text(json.dumps(registry_payload), encoding="utf-8")
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("data table" in error for error in result["errors"])
    sidecar_path.unlink()
    assert any(
        "missing data file" in error
        for error in validate_figure_registry(registry_path)["errors"]
    )


def test_svg_artifacts_expose_accessibility_metadata(tmp_path: Path) -> None:
    _, registry_path, registry = _registry_for(tmp_path, _mixed_report())
    root = registry_path.parent
    svg_paths = sorted(root.rglob("*.svg"))
    assert svg_paths
    for svg_path in svg_paths:
        text = svg_path.read_text(encoding="utf-8")
        assert 'role="img"' in text, svg_path.name
        assert "aria-labelledby" in text, svg_path.name
        assert "<title" in text and "<desc" in text, svg_path.name
    interval_entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    vector = (root / interval_entry["vector_path"]).read_text(encoding="utf-8")
    # Row labels and direct value labels survive as text, not baked into paths.
    assert "<text" in vector
    assert "Package valid" in vector
    assert re.search(r"<text[^>]*>\s*100\s*%", vector)


def test_single_series_uses_one_hue_and_marks_zero_and_na() -> None:
    svg = _bar_figure(
        "title",
        ["alpha", "beta", "gamma"],
        [1.0, 0.0, None],
        "unit",
        "subtitle",
        "alt description for the scene",
    )
    # Bar fills only: rects positioned on the chart, not the full-bleed
    # background rect. One hue for a single series.
    fills = set(re.findall(r'<rect x="[^"]*"[^>]*fill="([^"]+)"', svg))
    assert fills == {PALETTE[0]}
    assert "<circle" in svg  # a measured zero stays visible
    assert "N/A" in svg  # missing data is labelled, never drawn as zero
    grouped = _grouped_bar_figure(
        "title",
        ["alpha", "beta"],
        {"one": [1.0, 2.0], "two": [3.0, 4.0]},
        "unit",
        "subtitle",
        "alt description for the scene",
    )
    grouped_fills = set(re.findall(r'<rect x="[^"]*"[^>]*fill="([^"]+)"', grouped))
    assert len(grouped_fills) >= 2  # series identity is what color encodes


def test_missing_telemetry_is_labelled_not_zero(tmp_path: Path) -> None:
    report = build_evaluation_report(
        (
            _observation(
                metadata={"missing_metrics": ["generation_duration_ms"]},
            ),
        )
    )
    _, registry_path, registry = _registry_for(tmp_path, report)
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "generation-latency"
    )
    vector = (registry_path.parent / entry["vector_path"]).read_text(encoding="utf-8")
    assert "N/A" in vector
    assert entry["uncertainty"].strip()


def test_review_figure_gated_on_two_raters(tmp_path: Path) -> None:
    evidence = ("https://example.org/page",)
    _, unrated_path, unrated = _registry_for(tmp_path, _mixed_report())
    assert validate_figure_registry(unrated_path)["ok"]
    assert not any(
        item["figure_id"] == "human-review-rubric" for item in unrated["figures"]
    )
    rated = build_evaluation_report(
        _mixed_report().observations,
        ratings=(
            ReviewRating("case-1", "rater-1", 3, 3, 4, 4, 4, 3, evidence_urls=evidence),
            ReviewRating("case-1", "rater-2", 4, 3, 3, 4, 4, 4, evidence_urls=evidence),
        ),
    )
    _, rated_path, rated_registry = _registry_for(tmp_path / "rated", rated)
    validation = validate_figure_registry(rated_path)
    assert validation["ok"]
    assert validation["figure_count"] == 12
    review = next(
        item
        for item in rated_registry["figures"]
        if item["figure_id"] == "human-review-rubric"
    )
    assert review["sample_size"] == 2
    assert review["denominator"].strip()


def test_confidence_label_follows_report_policy(tmp_path: Path) -> None:
    report = _mixed_report()
    policy_report = replace(
        report,
        summary={**report.summary, "policy": {"confidence": 0.8}},
    )
    _, registry_path, registry = _registry_for(tmp_path, policy_report)
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    assert "80%" in entry["caption"]
    assert "95%" not in entry["caption"]
    assert entry["units"] == "percent with exact Clopper–Pearson 80% interval"


def test_proportion_alt_text_is_a_complete_sentence(tmp_path: Path) -> None:
    """Regression: the description used to begin mid-sentence ('places a dot…')."""
    _, _, registry = _registry_for(tmp_path, _mixed_report())
    entry = next(
        item
        for item in registry["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    alt = entry["alt_text"]
    assert not alt.startswith("places a dot")
    assert alt[:1].isupper()


def test_empirical_entries_carry_explicit_denominators(tmp_path: Path) -> None:
    """F1: the structural denominator default must not leak into empirical figures."""
    _, _, registry = _registry_for(tmp_path, _mixed_report())
    structural_default = "not applicable (contract-derived structural diagram)"
    structural_ids = {
        "pipeline-trust-boundaries",
        "run-state-machine",
        "cache-integrity-flow",
    }
    by_id = {item["figure_id"]: item for item in registry["figures"]}
    for figure_id, entry in by_id.items():
        assert entry["denominator"].strip()
        if figure_id in structural_ids:
            assert entry["denominator"] == structural_default
        else:
            assert entry["denominator"] != structural_default
    assert by_id["cache-integrity-flow"]["manuscript_refs"] == ["04_security"]
    assert by_id["provenance-completeness"]["manuscript_refs"] == ["05_evaluation"]


def test_axis_tick_helpers_use_integer_steps_for_counts() -> None:
    from skillarum.figures import _all_integral, _axis_ticks, _percent_ticks

    assert _axis_ticks(28.0, integral=True) == [0.0, 6.0, 12.0, 18.0, 24.0, 28.0]
    assert _percent_ticks() == [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    assert _axis_ticks(1.0, integral=True) == [0.0, 1.0]
    assert _axis_ticks(0.0, integral=True) == [0.0, 1.0]
    assert _all_integral([0.0, 5.0, None]) is True
    assert _all_integral([0.0, 1.11, None]) is False
    fractional = _axis_ticks(1.11, integral=False)
    assert len(fractional) == 5
    assert fractional[0] == 0.0
    assert fractional[-1] == 1.11


def test_every_entry_registers_a_hash_bound_raster_and_vector(
    tmp_path: Path,
) -> None:
    """F-A1 regression: a rendered companion must never be left unbound.

    Pre-fix, the source-overlap PNG renderer wrote its files but returned
    None, so the registry kept an SVG-canonical entry with no vector binding
    and the integrity manifest carried no PNG hash for that figure.
    """
    _, registry_path, registry = _registry_for(tmp_path, _mixed_report())
    assert validate_figure_registry(registry_path)["ok"]
    for entry in registry["figures"]:
        assert entry["path"].endswith(".png"), entry["figure_id"]
        assert entry["vector_path"].endswith(".svg"), entry["figure_id"]
        assert (registry_path.parent / entry["path"]).is_file()
        assert (registry_path.parent / entry["vector_path"]).is_file()
    manifest = json.loads(
        (registry_path.parent / "figure_registry.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in registry["figures"]:
        artifact = manifest["figure_artifacts"][entry["figure_id"]]
        assert artifact["path"].endswith(".png"), entry["figure_id"]
        assert artifact["artifact_sha256"] == entry["artifact_sha256"]
        assert artifact["vector_path"] == entry["vector_path"]
        assert artifact["vector_sha256"] == entry["vector_sha256"]


def test_validate_rejects_omitted_or_corrupt_raster(tmp_path: Path) -> None:
    report_path, registry_path, payload = _registry_for(tmp_path, _mixed_report())
    entry = next(
        item for item in payload["figures"] if item["figure_id"] == "area-catalog"
    )
    png = registry_path.parent / entry["path"]
    original = png.read_bytes()
    # Omitted companion: the registry binds a PNG that is missing on disk.
    png.unlink()
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("missing file" in error for error in result["errors"])
    # Corrupt companion: bytes no longer match the recorded hash.
    png.write_bytes(b"not a png")
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("artifact hash mismatch" in error for error in result["errors"])
    png.write_bytes(original)
    assert validate_figure_registry(registry_path)["ok"]


def test_count_axes_avoid_fractional_tick_labels(tmp_path: Path) -> None:
    """Negative control: pre-fix companions drew 0.25/1.2 ticks on count axes."""
    report = build_evaluation_report(
        (
            _observation(),
            _observation(
                observation_id="obs-2",
                case_id="case-2",
                target_id="other",
                run_id="run-2",
            ),
        )
    )
    _, _, _ = _registry_for(tmp_path, report)
    vector = (tmp_path / "figures/provider-fallback-outcomes.svg").read_text(
        encoding="utf-8"
    )
    assert ">0.25</text>" not in vector
    assert ">1.2</text>" not in vector
    assert ">1</text>" in vector


def test_percent_axes_never_suggest_above_100(tmp_path: Path) -> None:
    """Negative control: pre-fix percent axes spanned 0–120 with a 120 tick."""
    _, _, _ = _registry_for(tmp_path, _mixed_report())
    vector = (tmp_path / "figures/coverage-truncation.svg").read_text(encoding="utf-8")
    assert ">120</text>" not in vector
    assert ">100%</text>" in vector


def test_grouped_fallback_svg_marks_zero_and_na() -> None:
    svg = _grouped_bar_figure(
        "Title",
        ["alpha", "beta"],
        {"series one": [0.0, 2.0], "series two": [None, 1.0]},
        "count",
        "subtitle",
        "description",
    )
    # Exactly one measured zero: an explicit marker, never a missing category.
    assert svg.count("<circle") == 1
    assert "N/A" in svg


def test_interval_figure_states_row_denominators() -> None:
    from skillarum.figures import _interval_figure

    rows = [
        {
            "label": "Package valid",
            "total": 7,
            "successes": 7,
            "percent": 100.0,
            "exact_95_interval": [0.59, 1.0],
            "denominator_basis": "completed observations",
        },
        {
            "label": "No proportion records",
            "total": 0,
            "successes": 0,
            "percent": None,
            "exact_95_interval": None,
            "denominator_basis": "none",
        },
    ]
    svg = _interval_figure("Title", rows, "subtitle", "description")
    assert "denominator: completed observations" in svg
    assert "denominator: none" not in svg
    assert "no eligible denominator (n=0)" in svg


def test_latency_rows_group_by_area_then_target() -> None:
    from skillarum.figures import _latency_series

    report = build_evaluation_report(
        (
            _observation(
                observation_id="o1",
                case_id="c1",
                target_id="zeta",
                run_id="r1",
                metadata={"source_urls": ["https://x.test/a/", "https://x.test/b/"]},
                generation_duration_ms=3,
            ),
            _observation(
                observation_id="o2",
                case_id="c2",
                target_id="alpha",
                run_id="r2",
                area="Beta Area",
                generation_duration_ms=2,
            ),
            _observation(
                observation_id="o3",
                case_id="c3",
                target_id="mu",
                run_id="r3",
                area="Alpha Area",
                generation_duration_ms=1,
            ),
        )
    )
    labels, values = _latency_series(report)
    assert labels[0].startswith("Alpha Area")
    assert [label.split(" / ")[1] for label in labels] == ["Mu", "Alpha", "Zeta"]
    assert values == [1.0, 2.0, 3.0]


def test_source_overlap_matrix_matches_report_urls(tmp_path: Path) -> None:
    report = build_evaluation_report(
        (
            _observation(
                target_id="t-one",
                metadata={"source_urls": ["https://x.test/a/", "https://x.test/b/"]},
            ),
            _observation(
                observation_id="obs-2",
                case_id="case-2",
                target_id="t-two",
                run_id="run-2",
                metadata={"source_urls": ["https://x.test/b/", "https://x.test/c/"]},
            ),
            _observation(
                observation_id="obs-3",
                case_id="case-3",
                target_id="t-three",
                run_id="run-3",
                metadata={},
            ),
        )
    )
    _, registry_path, registry = _registry_for(tmp_path, report)
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        item for item in registry["figures"] if item["figure_id"] == "source-overlap"
    )
    assert entry["denominator"].strip()
    assert entry["alt_text"][:1].isupper()
    sidecar = json.loads(
        (registry_path.parent / entry["data_path"]).read_text(encoding="utf-8")
    )
    assert sidecar["figure_id"] == "source-overlap"
    by_pair = {(row["source_target"], row["target"]): row for row in sidecar["rows"]}
    assert by_pair[("T One", "T One")]["shared"] == 2
    assert by_pair[("T Two", "T Two")]["shared"] == 2
    assert by_pair[("T One", "T Two")]["shared"] == 1
    assert by_pair[("T One", "T Three")]["shared"] is None
    assert by_pair[("T One", "T Two")]["pages_source"] == 2
    # A target without a recorded list is unavailable, not zero.
    assert by_pair[("T Three", "T Three")]["pages_target"] is None


def test_source_overlap_gated_below_two_url_lists(tmp_path: Path) -> None:
    report = build_evaluation_report(
        (
            _observation(metadata={"source_urls": ["https://x.test/a/"]}),
            _observation(
                observation_id="obs-2",
                case_id="case-2",
                target_id="t-two",
                run_id="run-2",
            ),
        )
    )
    _, _, registry = _registry_for(tmp_path, report)
    assert all(item["figure_id"] != "source-overlap" for item in registry["figures"])
    assert not (tmp_path / "figures/source-overlap.svg").exists()
    assert not (tmp_path / "figures/figure_data/source-overlap.json").exists()


def test_source_overlap_recorded_empty_lists_are_measured_zeros(
    tmp_path: Path,
) -> None:
    """A recorded-but-empty URL list is usable evidence: zeros, not a gate-off.

    The gate counts observations that RECORD a source-URL list; only
    unrecorded telemetry is unavailable. This pins the predicate the
    manuscript prose states (05_evaluation): recorded lists count, empty
    lists are measured zeros, and fewer than two recorded lists suppress the
    figure entirely.
    """
    report = build_evaluation_report(
        (
            _observation(metadata={"source_urls": []}),
            _observation(
                observation_id="obs-2",
                case_id="case-2",
                target_id="t-two",
                run_id="run-2",
                metadata={"source_urls": []},
            ),
        )
    )
    _, registry_path, registry = _registry_for(tmp_path, report)
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        (item for item in registry["figures"] if item["figure_id"] == "source-overlap"),
        None,
    )
    assert entry is not None
    sidecar = json.loads(
        (registry_path.parent / entry["data_path"]).read_text(encoding="utf-8")
    )
    assert sidecar["rows"]
    assert all(row["shared"] == 0 for row in sidecar["rows"])


def test_validator_rejects_lowercase_alt_fragment(tmp_path: Path) -> None:
    report_path, registry_path, payload = _registry_for(tmp_path, _mixed_report())
    assert validate_figure_registry(registry_path)["ok"]
    entry = next(
        item
        for item in payload["figures"]
        if item["figure_id"] == "proportion-intervals"
    )
    entry["alt_text"] = "places a dot at the observed percentage near the edge"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_figure_registry(registry_path)
    assert not result["ok"]
    assert any("begin a descriptive sentence" in error for error in result["errors"])
