"""Real acquisition-to-manuscript builds and explicit failed-gate receipts."""

import json

import pytest

from skillarum.cli import main
from skillarum.pipeline import run_profile_from_path
from skillarum.publication import build_research_package


@pytest.fixture
def publication_project(tmp_path, fixture_server):
    project = tmp_path / "project"
    source = project / "docs/manuscript"
    source.mkdir(parents=True)
    (project / "data/evaluation").mkdir(parents=True)
    (project / "data/evaluation/cases.yaml").write_text("cases: []\n")
    (project / "data/citations.yaml").write_text("citations: []\n")
    (project / "data/claims.yaml").write_text("claims: []\n")
    (source / "references.bib").write_text("")
    (source / "config.yaml").write_text("paper:\n  title: Build fixture\n")
    (source / "01_body.md").write_text(
        "# Body\n\n{{OBSERVATION_COUNT}} observations.\n"
    )
    profile = project / "profile.yaml"
    profile.write_text(
        f"id: local\nname: Local\nbase_url: {fixture_server}\ncrawl:\n"
        "  allow_private_hosts: true\n  requests_per_second: 1000\n"
        "targets:\n  - id: page\n    name: Page\n    urls: ['/page']\n"
    )
    run_profile_from_path(profile, output_dir=project / "output")
    return project


def test_build_cli_repeat_preserves_artifacts_and_receipt(publication_project, capsys):
    project = publication_project
    output = project / "output"
    args = [
        "research",
        "build",
        "--project-root",
        str(project),
        "--output-dir",
        str(output),
        "--json",
    ]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["ok"] and first["render_status"] == "pending"
    assert all(step["ok"] for step in first["steps"])
    assert (
        output / "manuscript/01_body.md"
    ).read_text() == "# Body\n\n1 observations.\n"
    assert (output / "manuscript/config.yaml").read_bytes() == (
        project / "docs/manuscript/config.yaml"
    ).read_bytes()
    files = (
        sorted((output / "figures").glob("*.svg"))
        + sorted((output / "figures").glob("*.png"))
        + [output / "manuscript/01_body.md"]
    )
    assert files
    # Reports retain their build timestamp; scientific figure bytes and
    # hydrated data remain identical for fixed persisted observations.
    before = [path.read_bytes() for path in files]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert [path.read_bytes() for path in files] == before


def test_build_without_observations_overwrites_success_receipt(tmp_path):
    (tmp_path / "data/evaluation").mkdir(parents=True)
    (tmp_path / "data/evaluation/cases.yaml").write_text("cases: []\n")
    output = tmp_path / "output"
    receipt = output / "reports/research-build.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"ok": true}')
    with pytest.raises(ValueError, match="requires completed"):
        build_research_package(tmp_path, output)
    result = json.loads(receipt.read_text())
    assert result["ok"] is False
    assert result["steps"] == []


def test_malformed_archive_records_failed_receipt_and_completed_steps(
    publication_project,
):
    project = publication_project
    archive_root = project / "output/source_archives"
    archive_root.mkdir()
    (archive_root / "broken.json").write_text("{}")
    # The archive loader rejects a non-filename archive field with a typed
    # ValueError; the build must record a failed receipt with completed
    # steps instead of leaving stale success behind.
    with pytest.raises(ValueError, match="snapshot archive"):
        build_research_package(project, project / "output")
    receipt = json.loads((project / "output/reports/research-build.json").read_text())
    assert receipt["ok"] is False
    assert "ValueError" in receipt["error"]
    assert receipt["steps"][-1]["name"] == "manuscript_figures"


def test_binding_receipt_rejects_schema_and_report_mismatch(
    publication_project,
):
    from skillarum.manuscript import validate_manuscript_bindings

    project = publication_project
    build_research_package(project, project / "output")
    output = project / "output/manuscript"
    source = project / "docs/manuscript"
    registry = project / "output/figures/figure_registry.json"
    from skillarum.research import load_evaluation_report

    loaded = load_evaluation_report(project / "output/reports/evaluation-summary.json")
    check = validate_manuscript_bindings(
        source, output, loaded, project_root=project, figure_registry=registry
    )
    assert check["ok"], check["errors"]
    receipt_path = project / "output/data/manuscript_bindings.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["schema_version"] = 2
    receipt_path.write_text(json.dumps(receipt))
    check = validate_manuscript_bindings(
        source, output, loaded, project_root=project, figure_registry=registry
    )
    assert any("schema or report mismatch" in error for error in check["errors"])
    receipt = json.loads(receipt_path.read_text())
    receipt["schema_version"] = 1
    receipt["report_id"] = "forged-report"
    receipt_path.write_text(json.dumps(receipt))
    check = validate_manuscript_bindings(
        source, output, loaded, project_root=project, figure_registry=registry
    )
    assert any("schema or report mismatch" in error for error in check["errors"])


def test_input_change_during_build_fails_the_receipt(publication_project):
    import threading
    import time

    project = publication_project
    body = project / "docs/manuscript/01_body.md"

    def mutate():
        time.sleep(0.2)
        body.write_text("# Body\n\nMutated during build.\n")

    mutator = threading.Thread(target=mutate)
    mutator.start()
    with pytest.raises(ValueError, match="changed during build"):
        build_research_package(project, project / "output")
    mutator.join()
    receipt = json.loads((project / "output/reports/research-build.json").read_text())
    assert receipt["ok"] is False
    assert receipt["inputs"] != {}


def test_research_build_lock_serializes_concurrent_builders(publication_project):
    import threading
    import time

    from skillarum.utils import interprocess_lock

    project = publication_project
    output = project / "output"
    lock_path = output / ".locks/research-build.lock"
    receipt_path = output / "reports/research-build.json"
    with interprocess_lock(lock_path):
        holder = {"held": True}
        result: dict[str, object] = {}

        def blocked_build():
            build_research_package(project, output)
            holder["held"] = False

        worker = threading.Thread(target=blocked_build)
        worker.start()
        time.sleep(0.5)
        # The advisory lock is held, so the concurrent builder must still be
        # blocked before writing any receipt.
        assert holder["held"] is True
        assert not receipt_path.exists()
        result["still_blocked"] = worker.is_alive()
        assert result["still_blocked"] is True
    worker.join(timeout=120)
    assert not worker.is_alive()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["ok"] is True


def test_malformed_yaml_replaces_previous_success_receipt(tmp_path, capsys):
    (tmp_path / "data/evaluation").mkdir(parents=True)
    (tmp_path / "data/evaluation/cases.yaml").write_text("cases: [unterminated")
    receipt = tmp_path / "output/reports/research-build.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"ok": true}')
    with pytest.raises(ValueError, match="ParserError"):
        build_research_package(tmp_path, tmp_path / "output")
    result = json.loads(receipt.read_text())
    assert result["ok"] is False
    assert "ParserError" in result["error"]
    assert (
        main(
            [
                "research",
                "build",
                "--project-root",
                str(tmp_path),
                "--output-dir",
                str(tmp_path / "output"),
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["ok"] is False


@pytest.mark.parametrize(
    "bad_content,failed_gate",
    [
        ("# Body\n\n{{UNKNOWN_TOKEN}}", "manuscript"),
        ("# Body\n\n[@missing]", "bibliography"),
        ("# Body\n\n![Missing](../output/figures/absent.png)", "manuscript_figures"),
        (
            "# Body\n\n$$\nx = 1\n$$ {#eq:dup}\n\n$$\ny = 2\n$$ {#eq:dup}\n",
            "manuscript",
        ),
        ("# Body\n\nUnbalanced $ dollar.\n", "manuscript"),
    ],
)
def test_build_stops_at_invalid_source(publication_project, bad_content, failed_gate):
    project = publication_project
    (project / "docs/manuscript/01_body.md").write_text(bad_content)
    with pytest.raises(ValueError, match=failed_gate):
        build_research_package(project, project / "output")
    receipt = json.loads((project / "output/reports/research-build.json").read_text())
    assert receipt["ok"] is False
    assert receipt["steps"][-1]["name"] == failed_gate
    assert not (project / "output/manuscript/01_body.md").exists()


def test_install_rejects_symlinked_companion_directory(rendered_skill, tmp_path):
    import shutil
    from skillarum.install import install_skill

    package = tmp_path / "canonical" / rendered_skill.parent.name
    shutil.copytree(rendered_skill.parent, package)
    external = tmp_path / "external"
    external.mkdir()
    (external / "unapproved.txt").write_text("outside the package")
    (package / "linked").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        install_skill(package / "SKILL.md", "agents", home=tmp_path / "home")


def test_missing_fallback_telemetry_is_not_in_rate_denominator(publication_project):
    from dataclasses import replace
    from skillarum.research import collect_observations, summarize_observations

    original = collect_observations(publication_project / "output")[0]
    missing = replace(original, metadata={"missing_metrics": ["fallback_used"]})
    summary = summarize_observations((missing,))
    assert summary["fallback_rate"] is None
    assert summary["proportions"]["fallback_used"]["total"] == 0


def test_paired_ordinal_ratings_do_not_bootstrap_pooled_rows():
    from skillarum.research import ReviewRating, review_summary

    rows = tuple(
        ReviewRating(str(case), rater, case % 5, 4, 4, 4, 4, 4)
        for case in range(10)
        for rater in ("one", "two")
    )
    summary = review_summary(rows)
    assert summary["criteria"]["semantic_coverage"]["bootstrap_mean_interval"] is None
