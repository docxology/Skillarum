"""Real source-to-text reconstruction and forged binding negative controls."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from skillarum.manuscript import (
    manuscript_variables,
    render_manuscript,
    validate_manuscript_bindings,
    validate_manuscript_tree,
)
from skillarum.research import build_evaluation_report
from skillarum.utils import sha256_json


@pytest.fixture
def empty_report():
    return build_evaluation_report(())


@pytest.fixture
def manuscript_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.yaml").write_text(
        "manuscript_bindings:\n  forbid_numeric_prose: true\n"
    )
    (source / "01_body.md").write_text(
        "# Results\n\n{{OBSERVATION_COUNT}} observations; confidence {{CONFIDENCE_PERCENT}}.\n"
    )
    return source


@pytest.mark.parametrize(
    "text",
    [
        "{{ bad }}",
        "{{GOOD",
        "GOOD}}",
        "{{UNKNOWN}}",
        "73 observations",
        "Median duration: 2.7 ms",
        "Success rate is 95%.",
    ],
)
def test_invalid_prose_rejected_before_write(
    manuscript_source, empty_report, tmp_path, text
):
    (manuscript_source / "02_bad.md").write_text("# Bad\n\n" + text)
    assert not validate_manuscript_tree(manuscript_source)["ok"]
    output = tmp_path / "output/manuscript"
    with pytest.raises(ValueError):
        render_manuscript(manuscript_source, output, empty_report)
    assert not output.exists()


def test_syntax_constants_and_identifiers_are_not_measurements(manuscript_source):
    (manuscript_source / "02_math.md").write_text(
        "# Math {#sec:math}\n\n1. A definition: $x=0$.\n\n$$\nf(x)=1/2\n$$ {#eq:identity}\n\n"
        "Math 4 Wisdom uses SHA-256 and `02_prepare`. See [@source2026].\n\n"
        "```python\nx = 42\n```\n"
    )
    assert validate_manuscript_tree(manuscript_source)["ok"]


def test_reconstruction_rejects_rehashed_forgery(
    manuscript_source, empty_report, tmp_path
):
    output = tmp_path / "output/manuscript"
    render_manuscript(manuscript_source, output, empty_report)
    assert validate_manuscript_bindings(manuscript_source, output, empty_report)["ok"]
    receipt_path = output.parent / "data/manuscript_bindings.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["variables"]["OBSERVATION_COUNT"]["value"] = "999"
    receipt.pop("content_sha256")
    receipt["content_sha256"] = sha256_json(receipt)
    receipt_path.write_text(json.dumps(receipt))
    assert not validate_manuscript_bindings(manuscript_source, output, empty_report)[
        "ok"
    ]
    (output / "01_body.md").write_text("999 observations")
    check = validate_manuscript_bindings(manuscript_source, output, empty_report)
    assert any("hydrated text differs" in error for error in check["errors"])


def test_stale_sections_are_removed_and_overlap_rejected(
    manuscript_source, empty_report, tmp_path
):
    output = tmp_path / "output/manuscript"
    output.mkdir(parents=True)
    (output / "99_stale.md").write_text("obsolete")
    (output / "README.md").write_text("guidance")
    render_manuscript(manuscript_source, output, empty_report)
    assert sorted(path.name for path in output.glob("*.md")) == ["01_body.md"]
    for destination in (
        manuscript_source,
        manuscript_source / "child",
        manuscript_source.parent,
    ):
        with pytest.raises(ValueError, match="overlap"):
            render_manuscript(manuscript_source, destination, empty_report)


@pytest.mark.parametrize(
    "config",
    [
        "[]",
        "manuscript_bindings: []",
        "manuscript_bindings:\n  forbid_numeric_prose: 'true'",
    ],
)
def test_bad_binding_configuration_fails(manuscript_source, config):
    (manuscript_source / "config.yaml").write_text(config)
    assert not validate_manuscript_tree(manuscript_source)["ok"]


def test_empty_sources_missing_receipt_and_changed_input_fail(
    tmp_path, empty_report, manuscript_source
):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not validate_manuscript_tree(empty)["ok"]
    output = tmp_path / "output/manuscript"
    assert not validate_manuscript_bindings(manuscript_source, output, empty_report)[
        "ok"
    ]
    render_manuscript(manuscript_source, output, empty_report)
    (manuscript_source / "01_body.md").write_text("# Changed\n")
    assert not validate_manuscript_bindings(manuscript_source, output, empty_report)[
        "ok"
    ]


def test_configuration_and_statistical_policy_are_bound(tmp_path, empty_report):
    from skillarum.statistics import DEFAULT_POLICY

    profiles = tmp_path / "data/sources"
    profiles.mkdir(parents=True)
    (profiles / "sample.yaml").write_text(
        "id: sample\nname: Sample\nbase_url: https://example.org\n"
        "extraction:\n  max_chars_per_page: 12345\n"
        "targets:\n  - id: a\n    name: Target-A\n    urls: ['/page']\n    max_pages: 3\n"
    )
    values = manuscript_variables(empty_report, project_root=tmp_path)
    assert values["BOOTSTRAP_SEED"] == str(DEFAULT_POLICY.bootstrap_seed)
    assert values["CONFIGURED_TARGET_COUNT"] == "1"
    assert "12345" in values["PROFILE_CONFIGURATION_TABLE"]
    assert "unavailable" in values["PROPORTION_TABLE"]


def test_figure_bindings_reject_absent_and_wrong_report(tmp_path, empty_report):
    from skillarum.figures import generate_figures
    from skillarum.research import write_evaluation_report

    report_path = write_evaluation_report(empty_report, tmp_path)
    registry = generate_figures(
        empty_report, tmp_path / "figures", source_data=report_path
    )
    values = manuscript_variables(empty_report, figure_registry=registry)
    assert "FIGURE_PIPELINE_TRUST_BOUNDARIES_CAPTION" in values
    with pytest.raises(ValueError, match="different evaluation"):
        manuscript_variables(
            replace(empty_report, report_id="other"), figure_registry=registry
        )
    source = tmp_path / "source"
    source.mkdir()
    (source / "01_body.md").write_text("# Figure\n\n{{FIGURE_ABSENT_CAPTION}}")
    assert not validate_manuscript_tree(source, figure_registry=registry)["ok"]
    payload = json.loads(Path(registry).read_text())
    payload["figures"][0]["caption"] = "bad"
    Path(registry).write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="invalid figure registry"):
        manuscript_variables(empty_report, figure_registry=registry)


def test_nested_latex_and_companion_freshness(
    manuscript_source, empty_report, tmp_path
):
    body = manuscript_source / "01_body.md"
    body.write_text(
        "# Formula\n\n$\\frac{1}{\\sqrt{2}}$ and {{OBSERVATION_COUNT}} observations.\n"
    )
    bibliography = manuscript_source / "references.bib"
    bibliography.write_text("@misc{source, title={Source}}\n")
    output = tmp_path / "output/manuscript"
    render_manuscript(manuscript_source, output, empty_report)
    assert validate_manuscript_bindings(manuscript_source, output, empty_report)["ok"]
    (output / "references.bib").write_text("tampered")
    check = validate_manuscript_bindings(manuscript_source, output, empty_report)
    assert any("companion differs" in error for error in check["errors"])
    bibliography.unlink()
    (manuscript_source / "config.yaml").unlink()
    render_manuscript(manuscript_source, output, empty_report)
    assert not (output / "config.yaml").exists()
    assert not (output / "references.bib").exists()
    assert validate_manuscript_bindings(manuscript_source, output, empty_report)["ok"]


def test_input_snapshot_failure_cannot_leave_success_receipt(tmp_path):
    from skillarum.publication import build_research_package

    receipt = tmp_path / "output/reports/research-build.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"ok": true}')
    with pytest.raises(OSError):
        build_research_package(
            tmp_path, tmp_path / "output", ratings=(tmp_path / "missing.csv",)
        )
    assert json.loads(receipt.read_text())["ok"] is False


def test_observation_window_normalizes_offsets_and_marks_unknown():
    from skillarum.manuscript import _observation_window

    assert _observation_window(
        ["2026-09-07T23:50:00-07:00", "2026-09-08T01:00:00Z"]
    ) == ("2026-09-08T01:00:00+00:00", "2026-09-08T06:50:00+00:00")
    assert "invalid" in _observation_window(["bad"])[0]
    assert "UTC offset" in _observation_window(["2026-09-08T01:00:00"])[0]
    assert _observation_window([]) == ("unavailable", "unavailable")


def test_output_cannot_replace_authored_data(manuscript_source, empty_report, tmp_path):
    authored = tmp_path / "data"
    authored.mkdir()
    sentinel = authored / "manuscript_variables.json"
    sentinel.write_text("authored evidence")
    with pytest.raises(ValueError, match="overlap authored data"):
        render_manuscript(
            manuscript_source,
            tmp_path / "hydrated",
            empty_report,
            project_root=tmp_path,
        )
    assert sentinel.read_text() == "authored evidence"
    assert not (tmp_path / "hydrated").exists()


def test_invalid_profile_returns_binding_diagnostic(
    manuscript_source,
    empty_report,
    tmp_path,
):
    output = tmp_path / "output/manuscript"
    render_manuscript(manuscript_source, output, empty_report, project_root=tmp_path)
    profiles = tmp_path / "data/sources"
    profiles.mkdir(parents=True)
    (profiles / "broken.yaml").write_text("targets: [unterminated")
    result = validate_manuscript_bindings(
        manuscript_source,
        output,
        empty_report,
        project_root=tmp_path,
    )
    assert result["ok"] is False
    assert "invalid manuscript bindings" in result["errors"][-1]


def test_dangling_and_duplicate_crossreferences_fail(manuscript_source):
    (manuscript_source / "01_body.md").write_text(
        "# Body {#sec:body}\n\nSee [@eq:missing].\n\n$$\nx = 1\n$$ {#eq:present}\n"
    )
    check = validate_manuscript_tree(manuscript_source)
    assert not check["ok"]
    assert any(
        "undefined cross-reference label: eq:missing" in error
        for error in check["errors"]
    )
    (manuscript_source / "01_body.md").write_text(
        "# Body {#sec:body}\n\n$$\nx = 1\n$$ {#eq:twice}\n\n$$\ny = 2\n$$ {#eq:twice}\n"
    )
    check = validate_manuscript_tree(manuscript_source)
    assert any(
        "duplicate cross-reference label: eq:twice" in error
        for error in check["errors"]
    )


def test_manual_numbering_and_unbalanced_math_fail(manuscript_source):
    (manuscript_source / "01_body.md").write_text("# Body\n\n## 2.1 Broken\n")
    check = validate_manuscript_tree(manuscript_source)
    assert any("manual section numbering" in error for error in check["errors"])
    (manuscript_source / "01_body.md").write_text("# Body\n\nCost is $5 here.\n")
    check = validate_manuscript_tree(manuscript_source)
    assert any(
        "unbalanced inline or display math" in error for error in check["errors"]
    )


def test_sec_label_strictness_is_opt_in(manuscript_source):
    (manuscript_source / "config.yaml").write_text(
        "manuscript_bindings:\n  forbid_numeric_prose: false\n"
        "  require_sec_labels: true\n"
    )
    (manuscript_source / "01_body.md").write_text("# Unlabeled\n\nBody.\n")
    check = validate_manuscript_tree(manuscript_source)
    assert any("first heading must be" in error for error in check["errors"])
    (manuscript_source / "01_body.md").write_text("# Labeled {#sec:labeled}\n\nBody.\n")
    (manuscript_source / "preamble.md").write_text("Front matter without a heading.\n")
    assert validate_manuscript_tree(manuscript_source)["ok"]
    (manuscript_source / "02_other.md").write_text("# Other {#sec:labeled}\n\nBody.\n")
    check = validate_manuscript_tree(manuscript_source)
    assert any("duplicate section label: labeled" in error for error in check["errors"])
    (manuscript_source / "config.yaml").write_text(
        "manuscript_bindings:\n  require_sec_labels: 'true'\n"
    )
    assert not validate_manuscript_tree(manuscript_source)["ok"]


def test_hydration_requires_registry_for_figure_tokens(manuscript_source):
    (manuscript_source / "01_body.md").write_text(
        "# Body\n\n{{FIGURE_ABSENT_CAPTION}}\n"
    )
    assert validate_manuscript_tree(manuscript_source)["ok"]
    check = validate_manuscript_tree(manuscript_source, require_figure_registry=True)
    assert any(
        "figure caption tokens require a figure registry" in error
        for error in check["errors"]
    )


def test_binding_origin_families_are_declared():
    from skillarum.manuscript import _binding_origin

    assert _binding_origin("FIGURE_PIPELINE_TRUST_BOUNDARIES_CAPTION") == (
        "figure_registry.figures: pipeline-trust-boundaries"
    )
    assert _binding_origin("FIGURE_HUMAN_REVIEW_RUBRIC_ALT") == (
        "figure_registry.figures: human-review-rubric"
    )
    assert _binding_origin("PIPELINE_VERSION") == "executable package contract"
    assert _binding_origin("BOOTSTRAP_SEED") == "statistics.DEFAULT_POLICY"
    assert _binding_origin("REVIEW_CRITERION_COUNT") == "research.REVIEW_CRITERIA"
    assert _binding_origin("CONFIGURED_PROFILE_COUNT") == "data/sources/*.yaml"
    assert _binding_origin("SITE_REFRESH_SUMMARY") == (
        "hash-verified source archive receipts"
    )
    for key in ("OBSERVATION_COUNT", "RATING_STATUS", "BACKENDS_OBSERVED"):
        assert _binding_origin(key) == (
            "evaluation report observations and rederived summary"
        )


def test_known_tokens_cover_every_emitted_variable(tmp_path, empty_report):
    from skillarum.figures import generate_figures
    from skillarum.manuscript import (
        FIGURE_TOKEN_PATTERN,
        KNOWN_MANUSCRIPT_TOKENS,
    )
    from skillarum.research import write_evaluation_report

    profiles = tmp_path / "data/sources"
    profiles.mkdir(parents=True)
    (profiles / "sample.yaml").write_text(
        "id: sample\nname: Sample\nbase_url: https://example.org\n"
        "extraction:\n  max_chars_per_page: 4096\n"
        "targets:\n  - id: a\n    name: Target-A\n    urls: ['/page']\n"
    )
    report_path = write_evaluation_report(empty_report, tmp_path)
    registry = generate_figures(
        empty_report, tmp_path / "figures", source_data=report_path
    )
    values = manuscript_variables(
        empty_report, project_root=tmp_path, figure_registry=registry
    )
    # Figure caption/alt tokens are dynamic bindings validated against the
    # registry by name pattern; the static set covers the fixed vocabulary.
    dynamic = {token for token in values if FIGURE_TOKEN_PATTERN.fullmatch(token)}
    assert sorted(set(values) - KNOWN_MANUSCRIPT_TOKENS - dynamic) == []
