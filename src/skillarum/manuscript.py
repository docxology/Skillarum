"""Source-bound manuscript variables, validation, and hydration.

This module owns publication text binding; it does not acquire website content
or interpret generated skills as instructions. Research reexports its public
functions for API compatibility.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .utils import sha256_bytes, sha256_json, write_json_atomic, write_text_atomic

if TYPE_CHECKING:
    from .research import EvaluationReport

MANUSCRIPT_TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
KNOWN_MANUSCRIPT_TOKENS = {
    "REPORT_ID",
    "GENERATED_AT",
    "OBSERVATION_COUNT",
    "PROFILE_COUNT",
    "TARGET_COUNT",
    "PACKAGE_VALID_RATE",
    "FALLBACK_COUNT",
    "TRUNCATED_PAGES",
    "RATING_STATUS",
    "LIVE_OBSERVATION_COUNT",
    "EVIDENCE_ORIGINS",
    "OBSERVED_FROM",
    "OBSERVED_THROUGH",
    "SITE_REFRESH_SUMMARY",
    "PACKAGE_VERSION",
    "PIPELINE_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "CONFIDENCE_PERCENT",
    "ALPHA",
    "BOOTSTRAP_MINIMUM_N",
    "BOOTSTRAP_SEED",
    "BOOTSTRAP_RESAMPLES",
    "RATING_MINIMUM",
    "RATING_MAXIMUM",
    "RATING_SPAN",
    "RATING_CATEGORIES",
    "REVIEW_CRITERIA",
    "REVIEW_CRITERION_COUNT",
    "PROFILE_CONFIGURATION_TABLE",
    "CONFIGURED_PROFILE_COUNT",
    "CONFIGURED_TARGET_COUNT",
    "PROPORTION_TABLE",
    "TELEMETRY_TABLE",
    "PACKAGE_VALID_COUNT",
    "FALLBACK_ELIGIBLE_COUNT",
    "REVIEW_RATER_COUNT",
    "REVIEW_PAIRED_CASE_COUNT",
    "BACKENDS_OBSERVED",
    "STATISTICAL_POLICY_TABLE",
}
FIGURE_TOKEN_PATTERN = re.compile(r"FIGURE_[A-Z0-9_]+_(?:CAPTION|ALT)")

_CROSSREF_KINDS = (
    "sec",
    "fig",
    "eq",
    "tbl",
    "lst",
    "def",
    "prop",
    "thm",
    "lemma",
    "cor",
    "remark",
    "axiom",
    "claim",
    "example",
)
_CROSSREF_KINDS_PATTERN = "|".join(_CROSSREF_KINDS)
_CROSSREF_REF_PATTERN = re.compile(
    rf"(?<![\w])@((?:{_CROSSREF_KINDS_PATTERN}):([A-Za-z0-9:_-]+))"
)
_CROSSREF_LABEL_PATTERN = re.compile(
    rf"#((?:{_CROSSREF_KINDS_PATTERN}):([A-Za-z0-9:_-]+))"
)
_SEC_HEADING_PATTERN = re.compile(r"^#\s+.+\{#sec:([A-Za-z0-9_-]+)\}\s*$")


def _blank_match(match: re.Match[str]) -> str:
    """Blank a syntax region while preserving its line structure."""
    return "".join("\n" if char == "\n" else " " for char in match[0])


def _mask_structure_syntax(text: str) -> str:
    """Blank syntax regions that never carry cross-references or headings."""
    masked = MANUSCRIPT_TOKEN_PATTERN.sub(lambda m: " " * len(m[0]), text)
    for pattern in (
        r"(?ms)^```.*?^```[^\n]*",
        r"`[^`\n]+`",
        r"\]\([^)\n]*\)",
        r"https?://[^\s)\]>]+",
    ):
        masked = re.sub(pattern, _blank_match, masked)
    return masked


def _cell(value: object) -> str:
    """Keep source/configuration strings inside a Markdown table cell."""
    return str(value).replace("|", r"\|").replace("\n", " ").replace("\r", " ")


def _number(value: object) -> str:
    return (
        "unavailable"
        if value is None
        else f"{float(value):.2f}".rstrip("0").rstrip(".")
    )


def _table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        + ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    )


def manuscript_variables(
    report: EvaluationReport,
    *,
    site_summaries: tuple[dict, ...] = (),
    project_root: str | Path | None = None,
    figure_registry: str | Path | None = None,
) -> dict[str, str]:
    """Return deterministic manuscript tokens from a persisted report."""
    summary = report.summary
    valid_rate = summary.get("package_valid_rate")
    observed_from, observed_through = _observation_window(
        [item.observed_at for item in report.observations]
    )
    site_text = "No independently archived website inventory accompanies this report."
    if site_summaries:
        rows = [
            "| Website | Retained HTML pages | Discovered URLs | Recorded warnings |",
            "| --- | ---: | ---: | ---: |",
        ]
        for site in site_summaries:
            rows.append(
                f"| {site['profile_id']} | {site['accepted_pages']} | {site['discovered_urls']} | {len(site['warnings'])} |"
            )
        rows.extend(
            [
                "",
                "The Institute inventory follows its declared sitemap; the Math4Wisdom inventory follows query-free, same-origin links reachable from its seeds. Their discovery denominators differ. Raw responses, page records, and the acquisition receipts are retained in hash-checked local archives. These inventories are separate from the selected pages compiled into the selected skills. Warnings include excluded non-HTML responses, size limits, and unavailable URLs; they are not successful HTML acquisitions. Unlinked, protected, script-rendered, and excluded media content is outside this inventory.",
                "",
                "Acquisition windows (UTC; displayed to the second):",
                "",
                *[
                    f"- {site['profile_id']}: "
                    + datetime.fromisoformat(site["started_at"])
                    .astimezone(timezone.utc)
                    .strftime("%Y-%m-%d %H:%M:%S")
                    + " to "
                    + datetime.fromisoformat(site["finished_at"])
                    .astimezone(timezone.utc)
                    .strftime("%Y-%m-%d %H:%M:%S")
                    + "."
                    for site in site_summaries
                ],
            ]
        )
        site_text = "\n".join(rows)
    variables = {
        "SITE_REFRESH_SUMMARY": site_text,
        "OBSERVED_FROM": observed_from,
        "OBSERVED_THROUGH": observed_through,
        "EVIDENCE_ORIGINS": ", ".join(
            f"{kind}={count}"
            for kind, count in sorted(summary.get("source_types", {}).items())
            if count
        )
        or "none",
        "REPORT_ID": report.report_id,
        "GENERATED_AT": report.generated_at,
        "OBSERVATION_COUNT": str(summary.get("observation_count", 0)),
        "PROFILE_COUNT": str(summary.get("profile_count", 0)),
        "TARGET_COUNT": str(summary.get("target_count", 0)),
        "PACKAGE_VALID_RATE": "not available"
        if valid_rate is None
        else f"{valid_rate:.1%}",
        "FALLBACK_COUNT": str(summary.get("fallback_count", 0)),
        "TRUNCATED_PAGES": str(summary.get("truncated_pages", 0)),
        "RATING_STATUS": report.rating_status,
        "LIVE_OBSERVATION_COUNT": str(summary.get("source_types", {}).get("live", 0)),
    }
    from . import __version__
    from .pipeline import PIPELINE_VERSION
    from .render import MANIFEST_SCHEMA_VERSION
    from .research import REVIEW_CRITERIA
    from .statistics import DEFAULT_POLICY

    policy = DEFAULT_POLICY
    variables.update(
        {
            "PACKAGE_VERSION": __version__,
            "PIPELINE_VERSION": PIPELINE_VERSION,
            "MANIFEST_SCHEMA_VERSION": str(MANIFEST_SCHEMA_VERSION),
            "CONFIDENCE_PERCENT": f"{policy.confidence:.0%}",
            "ALPHA": f"{1 - policy.confidence:g}",
            "BOOTSTRAP_MINIMUM_N": str(policy.bootstrap_minimum_n),
            "BOOTSTRAP_SEED": str(policy.bootstrap_seed),
            "BOOTSTRAP_RESAMPLES": str(policy.bootstrap_resamples),
            "RATING_MINIMUM": str(policy.rating_minimum),
            "RATING_MAXIMUM": str(policy.rating_maximum),
            "RATING_SPAN": str(policy.rating_maximum - policy.rating_minimum),
            "RATING_CATEGORIES": ",".join(
                str(x) for x in range(policy.rating_minimum, policy.rating_maximum + 1)
            ),
            "REVIEW_CRITERIA": ", ".join(x.replace("_", " ") for x in REVIEW_CRITERIA),
            "REVIEW_CRITERION_COUNT": str(len(REVIEW_CRITERIA)),
            "PACKAGE_VALID_COUNT": str(summary.get("package_valid_count", 0)),
            "FALLBACK_ELIGIBLE_COUNT": str(
                summary.get("proportions", {}).get("fallback_used", {}).get("total", 0)
            ),
            "REVIEW_RATER_COUNT": str(summary.get("review", {}).get("rater_count", 0)),
            "REVIEW_PAIRED_CASE_COUNT": str(
                summary.get("review", {}).get("paired_case_count", 0)
            ),
            "BACKENDS_OBSERVED": ", ".join(
                sorted(
                    {
                        item.selected_backend or item.generator
                        for item in report.observations
                    }
                )
            )
            or "none",
        }
    )
    variables["STATISTICAL_POLICY_TABLE"] = _table(
        ("Setting", "Value"),
        [
            ("Reference interval confidence", variables["CONFIDENCE_PERCENT"]),
            ("Numerical bootstrap minimum sample", policy.bootstrap_minimum_n),
            ("Bootstrap seed", policy.bootstrap_seed),
            ("Bootstrap resamples", policy.bootstrap_resamples),
            (
                "Ordinal rubric bounds",
                f"{policy.rating_minimum} to {policy.rating_maximum}",
            ),
        ],
    )
    variables["PROPORTION_TABLE"] = _table(
        ("Check", "Passing / eligible", "Rate", "Model interval"),
        [
            (
                name.replace("_", " "),
                f"{item['successes']} / {item['total']}",
                "unavailable" if item["rate"] is None else f"{item['rate']:.1%}",
                "unavailable"
                if item.get("exact_95_interval") is None
                else " to ".join(f"{x:.1%}" for x in item["exact_95_interval"]),
            )
            for name, item in sorted((summary.get("proportions") or {}).items())
        ],
    )
    variables["TELEMETRY_TABLE"] = _table(
        ("Metric", "Recorded", "Missing", "Median", "Range"),
        [
            (
                label,
                summary[key]["n"],
                summary[key].get("missing_count", 0),
                _number(summary[key].get("median")),
                f"{_number(summary[key].get('min'))} to {_number(summary[key].get('max'))}",
            )
            for key, label in (
                ("request_count", "Request attempts"),
                ("response_bytes", "Response bytes"),
                ("generation_duration_ms", "Generation duration (ms)"),
            )
            if key in summary
        ],
    )
    if project_root is not None:
        from .config import load_profile

        profiles = [
            load_profile(path)
            for path in sorted((Path(project_root) / "data/sources").glob("*.yaml"))
        ]
        variables["CONFIGURED_PROFILE_COUNT"] = str(len(profiles))
        variables["CONFIGURED_TARGET_COUNT"] = str(
            sum(len(p.targets) for p in profiles)
        )
        variables["PROFILE_CONFIGURATION_TABLE"] = _table(
            ("Area / target", "Seed URLs", "Page limit", "Characters / page"),
            [
                (
                    f"{p.area or p.name} / {t.name}",
                    len(t.urls),
                    t.max_pages if t.max_pages is not None else p.crawl.max_pages,
                    p.extraction.max_chars_per_page,
                )
                for p in profiles
                for t in p.targets
            ],
        )
    if figure_registry is not None:
        from .figures import validate_figure_registry

        check = validate_figure_registry(figure_registry)
        if not check["ok"]:
            raise ValueError(f"invalid figure registry: {check['errors']}")
        registry = json.loads(Path(figure_registry).read_text(encoding="utf-8"))
        if registry.get("report_id") != report.report_id:
            raise ValueError("figure registry belongs to a different evaluation report")
        for figure in registry["figures"]:
            prefix = "FIGURE_" + str(figure["figure_id"]).replace("-", "_").upper()
            for suffix, field in (("CAPTION", "caption"), ("ALT", "alt_text")):
                key = f"{prefix}_{suffix}"
                if key in variables:
                    raise ValueError(f"duplicate manuscript binding: {key}")
                variables[key] = str(figure[field])
    return variables


def _observation_window(timestamps: list[str]) -> tuple[str, str]:
    """Normalize offsets before ordering; an unzoned time cannot establish UTC."""
    observed = []
    for value in timestamps:
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ("unavailable (invalid observation timestamp)",) * 2
        if instant.tzinfo is None:
            return ("unavailable (observation timestamp lacks a UTC offset)",) * 2
        observed.append(instant.astimezone(timezone.utc))
    if not observed:
        return "unavailable", "unavailable"
    return tuple(
        value.isoformat(timespec="seconds") for value in (min(observed), max(observed))
    )


def render_manuscript(
    source_dir: str | Path,
    output_dir: str | Path,
    report: EvaluationReport,
    *,
    site_summaries: tuple[dict, ...] = (),
    project_root: str | Path | None = None,
    figure_registry: str | Path | None = None,
) -> list[Path]:
    """Resolve manuscript tokens and reject unresolved or unknown variables."""
    source_root = Path(source_dir)
    destination_root = Path(output_dir)
    source_real, destination_real = source_root.resolve(), destination_root.resolve()
    if source_real.is_relative_to(destination_real) or destination_real.is_relative_to(
        source_real
    ):
        raise ValueError(
            "manuscript output must differ from and not overlap its authored source directory"
        )
    data_root = destination_root.parent / "data"
    protected_roots = [source_real]
    if project_root is not None:
        protected_roots.append((Path(project_root) / "data").resolve())
    if any(
        data_root.resolve().is_relative_to(protected)
        or protected.is_relative_to(data_root.resolve())
        for protected in protected_roots
    ):
        raise ValueError("manuscript binding output would overlap authored data")
    check = validate_manuscript_tree(
        source_root,
        figure_registry=figure_registry,
        require_figure_registry=True,
    )
    if not check["ok"]:
        raise ValueError("; ".join(check["errors"]))
    variables = manuscript_variables(
        report,
        site_summaries=site_summaries,
        project_root=project_root,
        figure_registry=figure_registry,
    )
    rendered: list[Path] = []
    paths = _manuscript_content_paths(source_root)
    if not paths:
        raise ValueError(f"manuscript directory has no Markdown files: {source_root}")
    # Resolve every section before writing, so even a malformed replacement
    # cannot leave a partially updated manuscript.
    resolved_sections: dict[str, str] = {}
    for source_path in paths:
        text = source_path.read_text(encoding="utf-8")
        unknown = set(MANUSCRIPT_TOKEN_PATTERN.findall(text)) - set(variables)
        if unknown:
            raise ValueError(
                f"{source_path} contains unknown manuscript tokens: {sorted(unknown)}"
            )
        resolved = MANUSCRIPT_TOKEN_PATTERN.sub(
            lambda match: variables[match.group(1)], text
        )
        if _unresolved_token_syntax(resolved):
            raise ValueError(f"{source_path} contains unresolved manuscript tokens")
        resolved_sections[source_path.name] = resolved
    for source_path in paths:
        destination = destination_root / source_path.name
        write_text_atomic(destination, resolved_sections[source_path.name])
        rendered.append(destination)
    # Remove guidance files from earlier renders so a rerun cannot leave them
    # on the publication surface after they are excluded from manuscript data.
    for stale in destination_root.glob("*.md"):
        if stale.name not in resolved_sections:
            stale.unlink()
    for companion in ("config.yaml", "references.bib"):
        source_path = source_root / companion
        if source_path.is_file():
            write_text_atomic(
                destination_root / companion, source_path.read_text(encoding="utf-8")
            )
        elif (destination_root / companion).exists() or (
            destination_root / companion
        ).is_symlink():
            (destination_root / companion).unlink()
    write_json_atomic(
        destination_root.parent / "data" / "manuscript_variables.json", variables
    )
    sources = _binding_sources(
        source_root, report, project_root, figure_registry, site_summaries
    )
    receipt = {
        "schema_version": 1,
        "report_id": report.report_id,
        "sources": sources,
        "variables": {
            key: {"value": value, "source": _binding_origin(key)}
            for key, value in sorted(variables.items())
        },
        "used_tokens": {
            path.name: sorted(
                set(MANUSCRIPT_TOKEN_PATTERN.findall(path.read_text(encoding="utf-8")))
            )
            for path in paths
        },
        "rendered": {path.name: sha256_bytes(path.read_bytes()) for path in rendered},
    }
    receipt["content_sha256"] = sha256_json(receipt)
    write_json_atomic(
        destination_root.parent / "data" / "manuscript_bindings.json", receipt
    )
    return rendered


def _binding_sources(
    source_root: Path,
    report: EvaluationReport,
    project_root: str | Path | None,
    figure_registry: str | Path | None,
    site_summaries: tuple[dict, ...],
) -> dict[str, Any]:
    paths = _manuscript_content_paths(source_root)
    sources = {
        str(path.relative_to(source_root)): sha256_bytes(path.read_bytes())
        for path in paths
    }
    sources["evaluation_content"] = report.artifact_sha256
    for module in (
        "manuscript.py",
        "statistics.py",
        "research.py",
        "figures.py",
        "pipeline.py",
        "render.py",
        "publication.py",
        "cli.py",
        "__init__.py",
    ):
        path = Path(__file__).with_name(module)
        sources[f"src/skillarum/{module}"] = sha256_bytes(path.read_bytes())
    for companion in ("config.yaml", "references.bib"):
        path = source_root / companion
        if path.is_file():
            sources[companion] = sha256_bytes(path.read_bytes())
    sources["site_archive_summaries"] = sha256_json(site_summaries)
    if figure_registry is not None:
        sources["figure_registry"] = sha256_bytes(Path(figure_registry).read_bytes())
    if project_root is not None:
        for path in sorted((Path(project_root) / "data/sources").glob("*.yaml")):
            sources[str(path.relative_to(project_root))] = sha256_bytes(
                path.read_bytes()
            )
    return sources


def _binding_origin(key: str) -> str:
    if key.startswith("FIGURE_"):
        return "figure_registry.figures: " + key.removeprefix("FIGURE_").rsplit("_", 1)[
            0
        ].lower().replace("_", "-")
    if key in {"PACKAGE_VERSION", "PIPELINE_VERSION", "MANIFEST_SCHEMA_VERSION"}:
        return "executable package contract"
    if (
        key.startswith(("BOOTSTRAP_", "RATING_"))
        and key != "RATING_STATUS"
        or key in {"ALPHA", "CONFIDENCE_PERCENT", "STATISTICAL_POLICY_TABLE"}
    ):
        return "statistics.DEFAULT_POLICY"
    if key.startswith("REVIEW_CRITER"):
        return "research.REVIEW_CRITERIA"
    if key.startswith(("CONFIGURED_", "PROFILE_CONFIGURATION")):
        return "data/sources/*.yaml"
    if key == "SITE_REFRESH_SUMMARY":
        return "hash-verified source archive receipts"
    return "evaluation report observations and rederived summary"


def validate_manuscript_bindings(
    source_dir: str | Path,
    output_dir: str | Path,
    report: EvaluationReport,
    *,
    project_root: str | Path | None = None,
    figure_registry: str | Path | None = None,
    site_summaries: tuple[dict, ...] = (),
) -> dict[str, Any]:
    """Compare hydrated text and binding receipts with their current sources.

    Hash consistency alone is insufficient: a forged value with a recomputed
    receipt hash still fails the independent reconstruction from report data.
    """
    source, output = Path(source_dir), Path(output_dir)
    errors: list[str] = []
    try:
        receipt = json.loads(
            (output.parent / "data/manuscript_bindings.json").read_text()
        )
        recorded_hash = receipt.pop("content_sha256", None)
        if recorded_hash != sha256_json(receipt):
            errors.append("manuscript binding receipt hash mismatch")
        if (
            receipt.get("schema_version") != 1
            or receipt.get("report_id") != report.report_id
        ):
            errors.append("manuscript binding receipt schema or report mismatch")
        variables = manuscript_variables(
            report,
            site_summaries=site_summaries,
            project_root=project_root,
            figure_registry=figure_registry,
        )
        expected_bindings = {
            key: {"value": value, "source": _binding_origin(key)}
            for key, value in variables.items()
        }
        if receipt.get("variables") != expected_bindings:
            errors.append(
                "manuscript bindings disagree with current evidence or contracts"
            )
        variable_file = json.loads(
            (output.parent / "data/manuscript_variables.json").read_text()
        )
        if variable_file != variables:
            errors.append("manuscript variable map disagrees with current evidence")
        paths = _manuscript_content_paths(source)
        if receipt.get("sources") != _binding_sources(
            source, report, project_root, figure_registry, site_summaries
        ):
            errors.append(
                "manuscript input hash inventory differs from current sources"
            )
        expected_tokens = {
            path.name: sorted(
                set(MANUSCRIPT_TOKEN_PATTERN.findall(path.read_text(encoding="utf-8")))
            )
            for path in paths
        }
        if receipt.get("used_tokens") != expected_tokens:
            errors.append("manuscript token inventory differs from source")
        for companion in ("config.yaml", "references.bib"):
            original, copy = source / companion, output / companion
            if original.is_file():
                if not copy.is_file() or original.read_bytes() != copy.read_bytes():
                    errors.append(
                        f"manuscript companion differs from source: {companion}"
                    )
            elif copy.exists() or copy.is_symlink():
                errors.append(f"stale manuscript companion: {companion}")
        expected_names = {path.name for path in paths}
        if {path.name for path in output.glob("*.md")} != expected_names:
            errors.append("hydrated manuscript section inventory differs from source")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            expected = MANUSCRIPT_TOKEN_PATTERN.sub(
                lambda match: variables[match[1]], text
            )
            actual = (output / path.name).read_text(encoding="utf-8")
            if actual != expected:
                errors.append(
                    f"hydrated text differs from current binding: {path.name}"
                )
            if receipt.get("sources", {}).get(path.name) != sha256_bytes(
                path.read_bytes()
            ):
                errors.append(f"manuscript source changed: {path.name}")
            if receipt.get("rendered", {}).get(path.name) != sha256_bytes(
                (output / path.name).read_bytes()
            ):
                errors.append(f"hydrated text hash differs from receipt: {path.name}")
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        yaml.YAMLError,
    ) as exc:
        errors.append(f"invalid manuscript bindings: {exc}")
    return {"ok": not errors, "errors": errors}


def _manuscript_content_paths(root: Path) -> list[Path]:
    """Return manuscript content while excluding local agent guidance."""
    excluded = {"AGENTS.md", "README.md", "MANUSCRIPT_STATUS.md", "SYNTAX.md"}
    return sorted(path for path in root.glob("*.md") if path.name not in excluded)


def validate_manuscript_tree(
    source_dir: str | Path,
    *,
    figure_registry: str | Path | None = None,
    require_figure_registry: bool = False,
) -> dict[str, Any]:
    """Validate manuscript tokens, structure, and optional figure references.

    Offline template-syntax contract: known and well-formed tokens, optional
    numeric-prose and section-label strictness, manual heading numbering,
    balanced math delimiters, duplicate ``{#kind:label}`` labels, and
    cross-references that resolve to a defined label.
    """
    root = Path(source_dir)
    errors: list[str] = []
    files = _manuscript_content_paths(root)
    if not files:
        errors.append(f"manuscript directory has no Markdown files: {root}")
    referenced_figures: set[str] = set()
    figure_tokens: set[str] = set()
    defined_labels: list[str] = []
    referenced_labels: set[str] = set()
    sec_labels: list[str] = []
    config_path = root / "config.yaml"
    config = (
        yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if config_path.is_file()
        else {}
    )
    if config is not None and not isinstance(config, dict):
        return {
            "ok": False,
            "file_count": len(files),
            "referenced_figures": [],
            "errors": ["manuscript config must be a mapping"],
        }
    binding_config = (config or {}).get("manuscript_bindings", {})
    if (
        not isinstance(binding_config, dict)
        or type(binding_config.get("forbid_numeric_prose", False)) is not bool
        or type(binding_config.get("require_sec_labels", False)) is not bool
    ):
        return {
            "ok": False,
            "file_count": len(files),
            "referenced_figures": [],
            "errors": [
                "manuscript_bindings requires a mapping with Boolean"
                " forbid_numeric_prose and require_sec_labels values"
            ],
        }
    strict_numbers = binding_config.get("forbid_numeric_prose", False)
    require_sec_labels = binding_config.get("require_sec_labels", False)
    for path in files:
        text = path.read_text(encoding="utf-8")
        tokens = set(MANUSCRIPT_TOKEN_PATTERN.findall(text))
        dynamic = {token for token in tokens if FIGURE_TOKEN_PATTERN.fullmatch(token)}
        figure_tokens.update(dynamic)
        unknown = sorted(tokens - KNOWN_MANUSCRIPT_TOKENS - dynamic)
        if unknown:
            errors.append(f"{path}: unknown manuscript tokens {unknown}")
        scrubbed = MANUSCRIPT_TOKEN_PATTERN.sub("", text)
        if _unresolved_token_syntax(scrubbed):
            errors.append(
                f"{path}: malformed manuscript token; use exact UPPERCASE_KEY syntax"
            )
        if strict_numbers and path.name != "preamble.md":
            for line_number, literal in _numeric_prose_literals(text):
                errors.append(
                    f"{path}:{line_number}: hard-coded numeric prose {literal!r}; bind a named variable"
                )
        masked_structure = _mask_structure_syntax(text)
        dollar_count = len(re.findall(r"(?<!\\)\$", masked_structure))
        if dollar_count % 2:
            errors.append(f"{path}: unbalanced inline or display math $ delimiters")
        if sum(1 for line in text.splitlines() if line.lstrip().startswith("```")) % 2:
            errors.append(f"{path}: unterminated code fence")
        for numbering in re.finditer(r"(?m)^#{1,6}\s+\d", masked_structure):
            errors.append(
                f"{path}: manual section numbering {numbering[0]!r};"
                " let the renderer number sections"
            )
        defined_labels.extend(
            match[1] for match in _CROSSREF_LABEL_PATTERN.finditer(masked_structure)
        )
        referenced_labels.update(
            match[1] for match in _CROSSREF_REF_PATTERN.finditer(masked_structure)
        )
        if require_sec_labels and path.name != "preamble.md":
            first_line = next((line for line in text.splitlines() if line.strip()), "")
            sec_match = _SEC_HEADING_PATTERN.match(first_line)
            if sec_match is None:
                errors.append(f"{path}: first heading must be '# Title {{#sec:label}}'")
            else:
                sec_labels.append(sec_match.group(1))
        referenced_figures.update(
            re.findall(r"output/figures/([A-Za-z0-9_.-]+\.(?:svg|png))", text)
        )
    if figure_registry:
        try:
            registry = json.loads(Path(figure_registry).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {
                "ok": False,
                "file_count": len(files),
                "referenced_figures": sorted(referenced_figures),
                "errors": [f"invalid figure registry: {exc}"],
            }
        if not isinstance(registry, dict):
            return {
                "ok": False,
                "file_count": len(files),
                "referenced_figures": sorted(referenced_figures),
                "errors": ["invalid figure registry: payload must be an object"],
            }
        available = {
            name
            for item in registry.get("figures", [])
            if isinstance(item, dict)
            for name in (
                Path(str(item.get("path", ""))).name,
                Path(str(item.get("raster_path", ""))).name,
                Path(str(item.get("vector_path", ""))).name,
            )
            if name != "."
        }
        for figure in sorted(referenced_figures - available):
            errors.append(
                f"manuscript references figure absent from registry: {figure}"
            )
        available_tokens = {
            "FIGURE_"
            + str(item.get("figure_id", "")).replace("-", "_").upper()
            + "_"
            + suffix
            for item in registry.get("figures", [])
            for suffix in ("CAPTION", "ALT")
        }
        for token in sorted(figure_tokens - available_tokens):
            errors.append(
                f"manuscript references caption absent from registry: {token}"
            )
    if figure_tokens and not figure_registry:
        message = "figure caption tokens require a figure registry: " + ", ".join(
            sorted(figure_tokens)
        )
        if require_figure_registry:
            errors.append(message)
    for label in sorted(referenced_labels - set(defined_labels)):
        errors.append(f"manuscript references undefined cross-reference label: {label}")
    for label, count in sorted(Counter(defined_labels).items()):
        if count > 1:
            errors.append(
                f"manuscript defines duplicate cross-reference label: {label}"
            )
    for label in sorted({s for s in sec_labels if sec_labels.count(s) > 1}):
        errors.append(f"manuscript defines duplicate section label: {label}")
    return {
        "ok": not errors,
        "file_count": len(files),
        "referenced_figures": sorted(referenced_figures),
        "errors": errors,
    }


def _unresolved_token_syntax(text: str) -> bool:
    """Catch broken placeholders without mistaking nested LaTeX for a token."""
    if "{{" in text:
        return True
    text = re.sub(r"(?s)\$\$.*?\$\$|\$[^$\n]+\$|(?m:^```[\s\S]*?^```[^\n]*)", "", text)
    return "}}" in text


def _numeric_prose_literals(text: str) -> list[tuple[int, str]]:
    """Find numeric prose while preserving mathematical constants and identifiers.

    Equations, code, citation keys, labels, URL paths, ordered-list markers,
    and proper names containing digits are syntax/identifiers, not observations.
    The guard complements named-variable tests; it is not a semantic proof that
    every English sentence has been correctly bound.
    """
    masked = MANUSCRIPT_TOKEN_PATTERN.sub(lambda m: " " * len(m[0]), text)

    def hide(match: re.Match[str]) -> str:
        return _blank_match(match)

    for pattern in (
        r"(?ms)^```.*?^```[^\n]*",
        r"(?s)\$\$.*?\$\$",
        r"\$[^$\n]+\$",
        r"`[^`\n]+`",
        r"\{#[^}]+\}",
        r"\]\([^)\n]*\)",
        r"https?://[^\s)\]>]+",
        r"@[A-Za-z][A-Za-z0-9:_-]*",
        r"(?m)^\s*\d+\.\s",
    ):
        masked = re.sub(pattern, hide, masked)
    # Public source's proper name and the algorithm identifier are stable names.
    masked = re.sub(r"Math\s+4\s+Wisdom|SHA-256", hide, masked)
    return [
        (masked.count("\n", 0, match.start()) + 1, match[0])
        for match in re.finditer(r"(?<![\w])\d+(?:[.,]\d+)*(?:%?)(?![\w])", masked)
    ]
