"""Ordered, offline construction of the research publication inputs."""

from pathlib import Path
from typing import Any

import yaml

from .pipeline import PIPELINE_VERSION
from .figures import generate_figures, validate_figure_registry
from .research import (
    build_evaluation_report,
    collect_observations,
    extract_manuscript_citations,
    load_bibliography_keys,
    load_cases,
    load_citations,
    load_claims,
    load_ratings,
    validate_bibliography,
    validate_ledgers,
    write_evaluation_report,
)
from .utils import interprocess_lock, sha256_bytes, write_json_atomic
from .site_snapshot import load_snapshot_archives
from .manuscript import (
    render_manuscript,
    validate_manuscript_bindings,
    validate_manuscript_tree,
)


def build_research_package(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    ratings: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Serialize builds and reject concurrent source changes before success."""
    project, output = Path(project_root), Path(output_dir)
    with interprocess_lock(output / ".locks/research-build.lock"):
        receipt_path = output / "reports/research-build.json"
        receipt: dict[str, Any] = {"ok": False, "steps": [], "render_status": "pending"}
        write_json_atomic(receipt_path, receipt)
        try:
            before = _build_inputs(project, ratings)
        except OSError as exc:
            receipt["error"] = f"input snapshot: {exc}"
            write_json_atomic(receipt_path, receipt)
            raise
        receipt = _build_research_package(project, output, ratings=ratings)
        try:
            after = _build_inputs(project, ratings)
        except OSError as exc:
            receipt["ok"] = False
            receipt["error"] = f"input snapshot after build: {exc}"
            write_json_atomic(receipt_path, receipt)
            raise
        receipt["inputs"] = before
        if before != after:
            receipt["ok"] = False
            receipt["error"] = (
                "research inputs changed during build; rebuild from a stable source snapshot"
            )
            write_json_atomic(output / "reports/research-build.json", receipt)
            raise ValueError(receipt["error"])
        write_json_atomic(output / "reports/research-build.json", receipt)
        return receipt


def _build_inputs(project: Path, ratings: tuple[Path, ...]) -> dict[str, str]:
    paths = {
        path
        for pattern in (
            "src/skillarum/*.py",
            "data/**/*.yaml",
            "docs/manuscript/*.md",
            "docs/manuscript/*.yaml",
            "docs/manuscript/*.bib",
            "pyproject.toml",
        )
        for path in project.glob(pattern)
        if path.is_file()
    }
    paths.update(ratings)
    return {
        str(
            path.relative_to(project) if path.is_relative_to(project) else path
        ): sha256_bytes(path.read_bytes())
        for path in sorted(paths)
    }


def _build_research_package(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    ratings: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Build report, figures, and hydrated sources; never acquire or publish.

    The receipt names every completed step. A failed step stops the build and
    replaces an earlier successful receipt with a failed receipt. Parent-template
    rendering and final publication-manifest validation are separate gates.
    """
    project, output = Path(project_root), Path(output_dir)
    receipt_path = output / "reports" / "research-build.json"
    receipt: dict[str, Any] = {"ok": False, "steps": [], "render_status": "pending"}
    try:
        cases = load_cases(project / "data/evaluation/cases.yaml")
        observations = collect_observations(
            output,
            pipeline_version=PIPELINE_VERSION,
            case_map={
                (case.profile_id, case.target_id): case.case_id for case in cases
            },
        )
        if not observations:
            raise ValueError("research build requires completed run observations")
        report = build_evaluation_report(
            observations,
            ratings=tuple(rating for path in ratings for rating in load_ratings(path)),
        )
        source = project / "docs/manuscript"
        citations = load_citations(project / "data/citations.yaml")
        checks = {
            "ledgers": validate_ledgers(
                citations,
                load_claims(project / "data/claims.yaml"),
                known_observation_ids={item.observation_id for item in observations},
                artifact_root=project,
            ),
            "bibliography": validate_bibliography(
                citations,
                load_bibliography_keys(source / "references.bib"),
                extract_manuscript_citations(source),
            ),
            "manuscript": validate_manuscript_tree(source),
        }
        for name, check in checks.items():
            receipt["steps"].append({"name": name, **check})
            if not check["ok"]:
                raise ValueError(f"{name}: {'; '.join(check['errors'])}")
        report_path = write_evaluation_report(report, output)
        receipt["report_id"] = report.report_id
        receipt["steps"].append(
            {"name": "evaluation", "ok": True, "path": str(report_path)}
        )
        registry = generate_figures(report, output / "figures", source_data=report_path)
        for name, check in (
            ("figures", validate_figure_registry(registry)),
            (
                "manuscript_figures",
                validate_manuscript_tree(source, figure_registry=registry),
            ),
        ):
            receipt["steps"].append({"name": name, **check})
            if not check["ok"]:
                raise ValueError(f"{name}: {'; '.join(check['errors'])}")
        sites = load_snapshot_archives(output)
        receipt["steps"].append(
            {"name": "site_archives", "ok": True, "count": len(sites)}
        )
        hydrated = render_manuscript(
            source,
            output / "manuscript",
            report,
            site_summaries=sites,
            project_root=project,
            figure_registry=registry,
        )
        receipt["steps"].append(
            {"name": "hydration", "ok": True, "files": [str(path) for path in hydrated]}
        )
        bindings = validate_manuscript_bindings(
            source,
            output / "manuscript",
            report,
            site_summaries=sites,
            project_root=project,
            figure_registry=registry,
        )
        receipt["steps"].append({"name": "manuscript_bindings", **bindings})
        if not bindings["ok"]:
            raise ValueError("; ".join(bindings["errors"]))
        receipt["ok"] = True
    except Exception as exc:
        # This is a receipt boundary, not a recovery path: preserve diagnostics
        # for unexpected parser/programming errors and always re-raise them.
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        write_json_atomic(receipt_path, receipt)
        if isinstance(exc, (yaml.YAMLError, TypeError)):
            raise ValueError(receipt["error"]) from exc
        raise
    return receipt
