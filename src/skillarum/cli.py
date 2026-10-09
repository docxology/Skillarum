"""Command-line interface for Skillarum."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from . import __version__
from .config import load_profile
from .exit_codes import EXIT_ENVIRONMENT, EXIT_FAILURE, EXIT_OK
from .figures import generate_figures, validate_figure_registry
from .pipeline import PIPELINE_VERSION, inspect_cache, run_profile_from_path
from .research import (
    build_evaluation_report,
    collect_observations,
    extract_manuscript_citations,
    load_claims,
    load_citations,
    load_cases,
    load_adjudications,
    load_bibliography_keys,
    load_evaluation_report,
    load_ratings,
    review_summary,
    validate_ledgers,
    validate_adjudications,
    validate_bibliography,
    validate_publication_manifest,
    write_evaluation_report,
    write_publication_manifest,
    write_rating_template,
)
from .generators import validate_generated_body
from .install import drift_report, harness_roots, install_skill
from .packdiff import diff_packages
from .policies import POLICY_PACKS, run_policies
from .render import validate_skill_package, write_skill_index
from .signature import verify_signature, write_signature
from .manuscript import render_manuscript, validate_manuscript_tree
from .site_snapshot import load_snapshot_archives


def _json_dump(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


TOP_LEVEL_COMMANDS = (
    "snapshot-site",
    "profile-from-index",
    "run",
    "validate",
    "verify",
    "mcp",
    "install",
    "drift",
    "pack",
    "index",
    "serve",
    "cache",
    "doctor",
    "evaluate",
    "figures",
    "research",
)


def _argv_wants_json() -> bool:
    """Peek sys.argv for --json: argparse errors happen before parsing,
    so the flag cannot be read from a parsed namespace yet."""
    return "--json" in sys.argv[1:]


def _argv_command() -> str | None:
    """Best-effort command name from sys.argv for argparse-level errors."""
    for token in sys.argv[1:]:
        if token in TOP_LEVEL_COMMANDS:
            return token
    return None


def _usage_error_payload(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": "usage_error",
        "error": message,
        "command": _argv_command(),
    }


def _error_payload(args: argparse.Namespace, exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "command": getattr(args, "command", None),
    }


class JSONArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that emits the structured JSON error shape on
    parse/usage failures when --json was requested on the command line."""

    def error(self, message: str) -> None:  # type: ignore[override]
        if _argv_wants_json():
            _json_dump(_usage_error_payload(message))
        super().error(message)


def _parser() -> argparse.ArgumentParser:
    parser = JSONArgumentParser(prog="skillarum")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser(
        "snapshot-site", help="Capture a fresh public HTML inventory with raw receipts"
    )
    snapshot.add_argument("--profile", type=Path, required=True)
    snapshot.add_argument("--seed", action="append", default=[])
    snapshot.add_argument("--sitemap")
    snapshot.add_argument("--output-dir", type=Path, required=True)
    snapshot.add_argument("--archive", type=Path)
    snapshot.add_argument("--archive-only", action="store_true")
    snapshot.add_argument("--max-pages", type=int, default=10000)
    snapshot.add_argument("--max-requests", type=int, default=20000)
    snapshot.add_argument("--json", action="store_true")

    from_index = subparsers.add_parser(
        "profile-from-index",
        help="derive one exact-page target per link listed on an index page",
    )
    from_index.add_argument("--profile", type=Path, required=True)
    from_index.add_argument("--index-url", required=True)
    from_index.add_argument(
        "--prefix", required=True, help="URL path prefix a listed page must have"
    )
    from_index.add_argument("--output", type=Path, required=True)
    from_index.add_argument("--profile-id", required=True)
    from_index.add_argument("--id-prefix", required=True)
    from_index.add_argument("--name-prefix", default="")
    from_index.add_argument(
        "--title-separator",
        help="keep only the text after the last separator in page titles",
    )
    from_index.add_argument(
        "--html",
        type=Path,
        help="parse a previously saved copy instead of fetching the index",
    )
    from_index.add_argument("--json", action="store_true")

    run = subparsers.add_parser("run", help="crawl targets and render skills")
    run.add_argument("--profile", required=True, type=Path)
    run.add_argument(
        "--backend",
        choices=("deterministic", "openai", "ollama", "command", "auto"),
        default=None,
        help="override the profile generation backend",
    )
    run.add_argument(
        "--fallback-backend",
        choices=("deterministic", "openai", "ollama", "command"),
        default=None,
        help="override the profile fallback backend",
    )
    run.add_argument(
        "--target",
        action="append",
        dest="targets",
        help="target id; repeat for multiple targets",
    )
    run.add_argument("--output-dir", type=Path, default=Path("output"))
    run.add_argument(
        "--refresh", action="store_true", help="ignore cached acquired bundles"
    )
    run.add_argument(
        "--force-process",
        action="store_true",
        help="rerun the selected generator even when a draft cache exists",
    )
    run.add_argument(
        "--model", default=None, help="override the profile provider model"
    )
    run.add_argument("--ollama-model", default=None)
    run.add_argument("--ollama-url", default=None)
    run.add_argument("--ollama-timeout", type=float, default=None)
    run.add_argument("--ollama-context", type=int, default=None)
    run.add_argument("--ollama-max-prompt-chars", type=int, default=None)
    run.add_argument(
        "--generator-command",
        nargs="+",
        help="executable and arguments for the command backend; receives JSON on stdin",
    )
    run.add_argument(
        "--json", action="store_true", help="emit a machine-readable run summary"
    )

    validate = subparsers.add_parser(
        "validate", help="validate one or more SKILL.md files"
    )
    validate.add_argument("paths", nargs="+", type=Path)
    validate.add_argument(
        "--json", action="store_true", help="emit machine-readable validation results"
    )

    verify = subparsers.add_parser(
        "verify",
        help="round-trip a rendered skill through all generation validators",
        description=(
            "Re-runs structural, provenance, safety, and non-leakage validation "
            "independent of any run. Exit 0 = verified, 1 = failed."
        ),
    )
    verify.add_argument("skill", type=Path, help="path to a SKILL.md")
    verify.add_argument(
        "--policy",
        action="append",
        dest="policies",
        choices=sorted(POLICY_PACKS),
        help="run a policy pack over the rendered content (repeatable)",
    )
    verify.add_argument(
        "--json", action="store_true", help="emit machine-readable verify report"
    )

    mcp = subparsers.add_parser(
        "mcp",
        help="run the Model Context Protocol stdio server",
        description="Expose bounded discovery, validation, resources, and prompts over JSON-RPC 2.0 stdio.",
    )
    mcp.add_argument(
        "--root",
        type=Path,
        help="filesystem root exposed by the server (default: current directory or SKILLARUM_MCP_ROOT)",
    )
    mcp.add_argument(
        "--allow-write",
        action="store_true",
        help="allow discovery-index rebuilds within the root",
    )

    install = subparsers.add_parser(
        "install",
        help="install a validated skill package into an agent harness root",
        description=(
            "Copies the validated package into the harness skills root and "
            "records a sidecar install manifest for drift detection."
        ),
    )
    install.add_argument("skill", type=Path, help="path to a SKILL.md")
    install.add_argument(
        "--harness",
        required=True,
        choices=sorted(harness_roots()),
        help="target harness",
    )
    install.add_argument(
        "--home", type=Path, help="home directory override (default: user home)"
    )
    install.add_argument(
        "--json", action="store_true", help="emit machine-readable install report"
    )

    drift = subparsers.add_parser(
        "drift",
        help="report installed-vs-canonical drift for an installed skill",
    )
    drift.add_argument("skill", type=Path, help="path to a SKILL.md")
    drift.add_argument(
        "--harness",
        required=True,
        choices=sorted(harness_roots()),
        help="target harness",
    )
    drift.add_argument(
        "--home", type=Path, help="home directory override (default: user home)"
    )
    drift.add_argument(
        "--json", action="store_true", help="emit machine-readable drift report"
    )

    pack = subparsers.add_parser(
        "pack",
        help="package a validated skill directory as a zip archive",
        description=(
            "Hard-gates on structural validation of the skill package before "
            "any archive is written; export is a trust boundary."
        ),
    )
    pack.add_argument("skill", type=Path, help="path to a SKILL.md")
    pack.add_argument("--zip", type=Path, help="output zip path (default: <skill>.zip)")
    pack.add_argument(
        "--packer",
        default="skillarum",
        help="packer identity recorded in the skillarum.sig pack signature",
    )
    pack.add_argument(
        "--verify-signature",
        action="store_true",
        help="verify the skillarum.sig pack signature after packing",
    )
    pack.add_argument(
        "--json", action="store_true", help="emit machine-readable pack report"
    )
    diff = subparsers.add_parser(
        "diff",
        help="compare two rendered skill packages at hash and section level",
        description=(
            "Compares every artifact in two rendered skill package directories "
            "by SHA-256, reports added/removed/changed files, and includes a "
            "section-level SKILL.md diff when the document changed."
        ),
    )
    diff.add_argument("old", type=Path, help="older rendered skill package directory")
    diff.add_argument("new", type=Path, help="newer rendered skill package directory")
    diff.add_argument(
        "--json", action="store_true", help="emit machine-readable diff output"
    )

    index = subparsers.add_parser(
        "index", help="rebuild the rendered skill discovery index"
    )
    index.add_argument("--skills-dir", type=Path, default=Path("output/skills"))
    index.add_argument(
        "--json", action="store_true", help="emit machine-readable index summary"
    )

    serve = subparsers.add_parser(
        "serve",
        help="serve the rendered skills directory over read-only HTTP",
        description=(
            "Start a read-only discovery server over the rendered skills "
            "directory and block until interrupted. --port 0 binds an "
            "ephemeral port."
        ),
    )
    serve.add_argument("--skills-dir", type=Path, default=Path("output/skills"))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--json", action="store_true", help="emit machine-readable serve summary"
    )

    cache = subparsers.add_parser("cache", help="inspect cache integrity")
    cache_subparsers = cache.add_subparsers(dest="cache_command", required=True)
    cache_inspect = cache_subparsers.add_parser(
        "inspect", help="report valid, stale, and corrupt caches"
    )
    cache_inspect.add_argument("--output-dir", type=Path, default=Path("output"))
    cache_inspect.add_argument(
        "--profile", type=Path, help="cross-check cache fingerprints against a profile"
    )
    cache_inspect.add_argument(
        "--json", action="store_true", help="emit machine-readable cache report"
    )

    doctor = subparsers.add_parser(
        "doctor",
        help="check profiles, outputs, Ollama, and credentials",
        description=(
            "Validates the profile, write-access to --output-dir and its .cache, and "
            "the Ollama endpoint. Note: this creates the output/cache directories and "
            "issues a live HTTP request to the Ollama /api/tags endpoint unless "
            "--no-network is given."
        ),
    )
    doctor.add_argument(
        "--profile",
        action="append",
        type=Path,
        help=(
            "profile YAML to validate; repeatable, and each argument may be a "
            "glob pattern (e.g. data/sources/*.yaml) for bulk validation"
        ),
    )
    doctor.add_argument("--output-dir", type=Path, default=Path("output"))
    doctor.add_argument("--ollama-url", default=None)
    doctor.add_argument("--ollama-model", default=None)
    doctor.add_argument("--timeout", type=float, default=3.0)
    doctor.add_argument(
        "--no-network",
        action="store_true",
        help=(
            "skip the Ollama /api/tags request; the output and .cache"
            " writeability check still runs and creates those directories"
        ),
    )
    doctor.add_argument(
        "--json", action="store_true", help="emit machine-readable doctor output"
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="aggregate completed runs into an evidence report"
    )
    evaluate.add_argument("--output-dir", type=Path, default=Path("output"))
    evaluate.add_argument(
        "--profile",
        action="append",
        type=Path,
        help="optional profile to run before aggregation; repeatable",
    )
    evaluate.add_argument(
        "--backend",
        choices=("deterministic", "openai", "ollama", "command", "auto"),
        default=None,
    )
    evaluate.add_argument("--target", action="append", dest="targets")
    evaluate.add_argument("--refresh", action="store_true")
    evaluate.add_argument(
        "--model", default=None, help="override the profile provider model"
    )
    evaluate.add_argument(
        "--fallback-backend",
        choices=("deterministic", "openai", "ollama", "command"),
        default=None,
        help="override the profile fallback backend",
    )
    evaluate.add_argument(
        "--generator-command",
        nargs="+",
        help="executable and arguments for the command backend when a profile is run",
    )
    evaluate.add_argument("--ollama-model", default=None)
    evaluate.add_argument("--ollama-url", default=None)
    evaluate.add_argument("--ollama-timeout", type=float, default=None)
    evaluate.add_argument("--ollama-context", type=int, default=None)
    evaluate.add_argument("--ollama-max-prompt-chars", type=int, default=None)
    evaluate.add_argument(
        "--live",
        action="store_true",
        help="explicitly permit public live-profile acquisition",
    )
    evaluate.add_argument(
        "--ratings",
        action="append",
        type=Path,
        help="optional rater CSV file; repeat for independent raters",
    )
    evaluate.add_argument(
        "--cases",
        type=Path,
        default=Path("data/evaluation/cases.yaml"),
        help="declarative live-matrix case plan mapping profile/target keys to case ids",
    )
    evaluate.add_argument("--json", action="store_true")

    figures = subparsers.add_parser(
        "figures", help="generate deterministic SVG figures from an evaluation report"
    )
    figures.add_argument("--evaluation", type=Path, required=True)
    figures.add_argument("--output-dir", type=Path, default=Path("output/figures"))
    figures.add_argument("--json", action="store_true")

    research = subparsers.add_parser(
        "research", help="validate scholarly ledgers and publication metadata"
    )
    research_subparsers = research.add_subparsers(
        dest="research_command", required=True
    )
    research_validate = research_subparsers.add_parser(
        "validate", help="validate citations, claims, and figures"
    )
    research_validate.add_argument(
        "--citations", type=Path, default=Path("data/citations.yaml")
    )
    research_validate.add_argument(
        "--claims", type=Path, default=Path("data/claims.yaml")
    )
    research_validate.add_argument(
        "--figures", type=Path, default=Path("output/figures/figure_registry.json")
    )
    research_validate.add_argument("--evaluation", type=Path)
    research_validate.add_argument(
        "--manuscript-dir", type=Path, default=Path("docs/manuscript")
    )
    research_validate.add_argument("--bibliography", type=Path)
    research_validate.add_argument(
        "--ratings",
        action="append",
        type=Path,
        help="rater CSV file; repeat when ratings are split across files",
    )
    research_validate.add_argument("--adjudication", type=Path)
    research_validate.add_argument(
        "--publication",
        type=Path,
        default=Path("output/reports/publication-manifest.json"),
    )
    research_validate.add_argument("--json", action="store_true")
    research_rating = research_subparsers.add_parser(
        "ratings-template", help="write a blank human-review CSV"
    )
    research_rating.add_argument(
        "--output", type=Path, default=Path("data/evaluation/ratings.csv")
    )
    research_rating.add_argument("--case", action="append", required=True)
    research_rating.add_argument("--json", action="store_true")
    research_manuscript = research_subparsers.add_parser(
        "manuscript", help="resolve and validate manuscript sources"
    )
    research_manuscript.add_argument("--evaluation", type=Path, required=True)
    research_manuscript.add_argument(
        "--source-dir", type=Path, default=Path("docs/manuscript")
    )
    research_manuscript.add_argument(
        "--output-dir", type=Path, default=Path("output/manuscript")
    )
    research_manuscript.add_argument(
        "--figures", type=Path, default=Path("output/figures/figure_registry.json")
    )
    research_manuscript.add_argument("--render", action="store_true")
    research_manuscript.add_argument("--json", action="store_true")
    research_manuscript.add_argument("--project-root", type=Path, default=Path("."))
    research_build = research_subparsers.add_parser(
        "build", help="build and validate research inputs in dependency order (offline)"
    )
    research_build.add_argument("--project-root", type=Path, default=Path("."))
    research_build.add_argument("--output-dir", type=Path, default=Path("output"))
    research_build.add_argument("--ratings", action="append", type=Path)
    research_build.add_argument("--json", action="store_true")
    research_publication = research_subparsers.add_parser(
        "publication", help="hash and validate publication outputs"
    )
    research_publication.add_argument("--output-dir", type=Path, default=Path("output"))
    research_publication.add_argument("--project-root", type=Path, default=Path("."))
    research_publication.add_argument(
        "--require-rendered",
        action="store_true",
        help="require configured PDF/HTML artifacts",
    )
    research_publication.add_argument("--json", action="store_true")
    return parser


def _find_run_manifest(output_dir: Path, skills: list[Path]) -> dict[str, Any] | None:
    wanted = {str(path) for path in skills}
    manifests = list((output_dir / "runs").glob("*/manifest.json"))
    manifests.sort(
        key=lambda path: path.stat().st_mtime_ns if path.exists() else 0,
        reverse=True,
    )
    for path in manifests:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, dict)
            and value.get("pipeline_version") == PIPELINE_VERSION
            and value.get("state") == "rendered"
            and wanted.issubset(set(value.get("targets", [])))
        ):
            return value
    return None


def _load_rating_files(paths: list[Path] | None) -> tuple[Any, ...]:
    """Load and combine rating files while preserving the one-row-per-rater contract."""
    ratings = tuple(item for path in paths or [] for item in load_ratings(path))
    keys = [(item.case_id, item.rater_id) for item in ratings]
    if len(set(keys)) != len(keys):
        raise ValueError(
            "rating case_id and rater_id pairs must be unique across rating files"
        )
    return ratings


def _doctor_profiles(args: argparse.Namespace) -> tuple[list[dict[str, Any]], Any]:
    """Load every requested profile (globs expanded) into per-profile records."""
    profile_paths: list[Path] = []
    for pattern in args.profile or []:
        matches = (
            sorted(Path(pattern).parent.glob(Path(pattern).name))
            if any(ch in str(pattern) for ch in "*?[")
            else [pattern]
        )
        if not matches:
            matches = [pattern]
        profile_paths.extend(matches)
    profiles: list[dict[str, Any]] = []
    loaded: list[Any] = []
    if not profile_paths:
        profiles.append({"name": "profile", "path": None, "ok": True, "skipped": True})
        return profiles, None
    for profile_path in profile_paths:
        try:
            profile = load_profile(profile_path)
            profiles.append(
                {
                    "name": "profile",
                    "ok": True,
                    "path": str(profile_path),
                    "profile_id": profile.id,
                    "targets": len(profile.targets),
                }
            )
            loaded.append(profile)
        except Exception as exc:
            profiles.append(
                {
                    "name": "profile",
                    "ok": False,
                    "path": str(profile_path),
                    "error": str(exc),
                }
            )
    return profiles, (loaded[0] if loaded else None)


def _doctor(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    checks: list[dict[str, Any]] = []
    profile = None
    profile_results, first_profile = _doctor_profiles(args)
    profile = first_profile
    checks.extend(profile_results)

    for directory_name, directory in (
        ("output", args.output_dir),
        (".cache", args.output_dir / ".cache"),
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=directory, prefix=".doctor-", delete=True
            ):
                pass
            checks.append(
                {
                    "name": f"{directory_name}_writeability",
                    "ok": True,
                    "path": str(directory),
                }
            )
        except OSError as exc:
            checks.append(
                {
                    "name": f"{directory_name}_writeability",
                    "ok": False,
                    "error": str(exc),
                }
            )

    generation = profile.generation if profile else None
    ollama_url = (
        args.ollama_url
        or (generation.ollama_url if generation else None)
        or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    ollama_model = (
        args.ollama_model
        or (generation.ollama_model if generation else None)
        or os.getenv("OLLAMA_MODEL", "llama3.2")
    )
    if "://" not in ollama_url:
        ollama_url = f"http://{ollama_url}"
    parsed_ollama_url = urlparse(ollama_url)
    url_error = None
    if (
        parsed_ollama_url.scheme not in {"http", "https"}
        or not parsed_ollama_url.netloc
        or parsed_ollama_url.username
        or parsed_ollama_url.password
        or any(character.isspace() for character in ollama_url)
    ):
        url_error = "Ollama URL must be an absolute http(s) URL without credentials"
    if url_error:
        checks.append({"name": "ollama_endpoint", "ok": False, "error": url_error})
    elif args.no_network:
        checks.append({"name": "ollama_endpoint", "ok": True, "skipped": True})
    else:
        try:
            response = httpx.get(
                f"{ollama_url.rstrip('/')}/api/tags", timeout=args.timeout
            )
            response.raise_for_status()
            payload = response.json()
            models = [
                str(item.get("name"))
                for item in payload.get("models", [])
                if isinstance(item, dict)
            ]
            present = ollama_model in models or ollama_model.split(":", 1)[0] in {
                item.split(":", 1)[0] for item in models
            }
            checks.append(
                {
                    "name": "ollama_endpoint",
                    "ok": present,
                    "url": ollama_url,
                    "model": ollama_model,
                    "model_present": present,
                    "models": models,
                }
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            checks.append(
                {
                    "name": "ollama_endpoint",
                    "ok": False,
                    "url": ollama_url,
                    "error": str(exc),
                    "network_failure": True,
                }
            )

    openai_configured = bool(os.getenv("OPENAI_API_KEY"))
    openai_backend_selected = bool(generation) and generation.backend == "openai"
    openai_check = {
        "name": "openai_configuration",
        "ok": openai_configured or not openai_backend_selected,
        "configured": openai_configured,
        "secret_persisted": False,
    }
    if not openai_configured and bool(generation) and generation.backend == "auto":
        openai_check["note"] = (
            "auto backend does not require OPENAI_API_KEY; it degrades to Ollama, "
            "then the deterministic generator"
        )
    checks.append(openai_check)
    report = {
        "ok": all(bool(check.get("ok")) for check in checks),
        "checks": checks,
        "profiles": profile_results,
    }
    if report["ok"]:
        return report, EXIT_OK
    network_failed = any(check.get("network_failure") for check in checks)
    if network_failed:
        return report, EXIT_ENVIRONMENT
    return report, EXIT_FAILURE


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot-site":
            from .site_snapshot import archive_site_snapshot, scrape_site

            profile = load_profile(args.profile)
            if args.archive_only:
                if not args.archive:
                    raise ValueError("--archive-only requires --archive")
            else:
                scrape_site(
                    profile,
                    args.output_dir,
                    seed_urls=tuple(args.seed) or (profile.base_url,),
                    sitemap_url=args.sitemap,
                    max_pages=args.max_pages,
                    max_requests=args.max_requests,
                    progress=None if args.json else print,
                )
            result = (
                archive_site_snapshot(args.output_dir, args.archive)
                if args.archive
                else json.loads((args.output_dir / "snapshot.json").read_text())
            )
            _json_dump(result)
            return EXIT_OK if result["complete"] else EXIT_FAILURE
        if args.command == "profile-from-index":
            from .index_profile import write_index_profile

            result = write_index_profile(
                load_profile(args.profile),
                index_url=args.index_url,
                prefix=args.prefix,
                output=args.output,
                profile_id=args.profile_id,
                id_prefix=args.id_prefix,
                name_prefix=args.name_prefix,
                html_path=args.html,
                title_separator=args.title_separator,
            )
            if args.json:
                _json_dump(result)
            else:
                print(f"{result['entry_count']} targets written to {result['output']}")
            return EXIT_OK
        if args.command == "run":
            paths = run_profile_from_path(
                args.profile,
                output_dir=args.output_dir,
                backend=args.backend,
                target_ids=args.targets,
                refresh=args.refresh,
                force_process=args.force_process,
                model=args.model,
                command=args.generator_command,
                fallback_backend=args.fallback_backend,
                ollama_model=args.ollama_model,
                ollama_url=args.ollama_url,
                ollama_timeout_seconds=args.ollama_timeout,
                ollama_num_ctx=args.ollama_context,
                ollama_max_prompt_chars=args.ollama_max_prompt_chars,
            )
            summary = {"ok": True, "skills": [str(path) for path in paths]}
            manifest = _find_run_manifest(args.output_dir, paths)
            if manifest:
                summary["run"] = manifest
            if args.json:
                _json_dump(summary)
            else:
                for path in paths:
                    print(path)
            return EXIT_OK
        if args.command == "index":
            path = write_skill_index(args.skills_dir)
            result = {"ok": True, "index": str(path)}
            if args.json:
                _json_dump(result)
            else:
                print(path)
            return EXIT_OK
        if args.command == "verify":
            skill_path = args.skill
            checks: list[dict[str, Any]] = []
            try:
                validate_skill_package(skill_path)
                checks.append({"name": "package_validation", "ok": True})
            except (OSError, ValueError, RuntimeError) as exc:
                report = {
                    "ok": False,
                    "skill": str(skill_path),
                    "checks": [
                        {
                            "check": "package_validation",
                            "ok": False,
                            "error": str(exc),
                        }
                    ],
                }
                if args.json:
                    _json_dump(report)
                else:
                    print(f"verify failed: {exc}", file=sys.stderr)
                return EXIT_FAILURE
            try:
                body = skill_path.read_text(encoding="utf-8").split("---\n", 2)[-1]
                validate_generated_body(body, provider_output=False)
                checks.append({"name": "generation_body", "ok": True})
            except (OSError, ValueError, RuntimeError) as exc:
                results = [{"check": "generation_body", "ok": False, "error": str(exc)}]
                report = {"ok": False, "skill": str(skill_path), "checks": results}
                if args.json:
                    _json_dump(report)
                else:
                    print(f"verify failed: {exc}", file=sys.stderr)
                return EXIT_FAILURE
            if getattr(args, "policies", None):
                policy_report = run_policies(
                    args.policies, skill_path.read_text(encoding="utf-8")
                )
                checks.append(
                    {
                        "name": "policy",
                        "ok": policy_report["ok"],
                        "policy": policy_report["policies"],
                        "error_count": policy_report["error_count"],
                        "warning_count": policy_report["warning_count"],
                        "findings": policy_report["findings"],
                    }
                )
                if not policy_report["ok"]:
                    report = {"ok": False, "skill": str(skill_path), "checks": checks}
                    if args.json:
                        _json_dump(report)
                    else:
                        print("verify failed on policy", file=sys.stderr)
                        for finding in policy_report["findings"]:
                            if finding["severity"] == "error":
                                print(
                                    f"  {finding['rule']}: {finding['message']}",
                                    file=sys.stderr,
                                )
                    return EXIT_FAILURE
            report = {"ok": True, "skill": str(skill_path), "checks": checks}
            if args.json:
                _json_dump(report)
            else:
                print("verify: ok")
                for check in checks:
                    print(f"ok {check['name']}")
            return EXIT_OK
        if args.command == "mcp":
            from .mcp_server import serve_stdio

            return serve_stdio(args.root, allow_write=args.allow_write)
        if args.command == "install":
            manifest = install_skill(args.skill, args.harness, home=args.home)
            if args.json:
                _json_dump({"ok": True, **manifest})
            else:
                print(f"installed: {manifest['installed_path']}")
                print(f"tree hash: {manifest['installed_tree_hash']}")
            return EXIT_OK
        if args.command == "drift":
            report = drift_report(args.skill, args.harness, home=args.home)
            if args.json:
                _json_dump(report)
            else:
                print("drift: " + ("ok" if report["ok"] else "drifted"))
                for issue in report["issues"]:
                    print(f"  {issue['code']}: {issue['message']} -> {issue['action']}")
            return EXIT_OK if report["ok"] else EXIT_FAILURE
        if args.command == "diff":
            package_diff = diff_packages(args.old, args.new)
            payload = package_diff.to_dict()
            if args.json:
                _json_dump(payload)
            else:
                print(f"old: {payload['old_path']}")
                print(f"new: {payload['new_path']}")
                print(f"identical: {payload['identical']}")
                print(f"added ({len(payload['added'])}):")
                for name in payload["added"]:
                    print(f"  + {name}")
                print(f"removed ({len(payload['removed'])}):")
                for name in payload["removed"]:
                    print(f"  - {name}")
                print(f"changed ({len(payload['changed'])}):")
                for name in payload["changed"]:
                    print(f"  ~ {name}")
                print(f"unchanged: {payload['unchanged_count']}")
                if payload["skill_section_changes"]:
                    print("SKILL.md section changes:")
                    for title, change in payload["skill_section_changes"].items():
                        print(f"  [{change['status']}] {title}")
            return EXIT_OK if payload["identical"] else EXIT_FAILURE
        if args.command == "pack":
            import zipfile

            skill_path = args.skill
            try:
                validate_skill_package(skill_path)
            except (OSError, ValueError, RuntimeError) as exc:
                if args.json:
                    _json_dump(
                        {
                            **_error_payload(args, exc),
                            "skill": str(skill_path),
                        }
                    )
                else:
                    print(f"pack refused (validation failed): {exc}", file=sys.stderr)
                return EXIT_FAILURE
            package_dir = skill_path.resolve().parent
            zip_path = Path(args.zip) if args.zip else skill_path.with_suffix(".zip")
            zip_real = zip_path.resolve()
            excluded_archives: list[str] = []
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(package_dir.rglob("*")):
                    if not file_path.is_file():
                        continue
                    relative = file_path.relative_to(package_dir)
                    if any(part.startswith(".") for part in relative.parts):
                        continue
                    if file_path.resolve() == zip_real:
                        continue
                    if file_path.suffix.lower() == ".zip":
                        excluded_archives.append(str(relative))
                        continue
                    zf.write(file_path, relative)
            signature = write_signature(zip_path, packer=args.packer)
            # write_signature rewrites the archive; hash the delivered bytes.
            digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
            report = {
                "ok": True,
                "skill": str(skill_path),
                "archive": str(zip_path),
                "sha256": digest,
                "excluded_archives": excluded_archives,
                "pack_signature": {
                    "member": "skillarum.sig",
                    "packer": signature.packer,
                    "pack_hash": signature.pack_hash,
                    "member_count": signature.member_count,
                },
            }
            if args.verify_signature:
                verification = verify_signature(zip_path)
                report["signature_verification"] = verification
                if not verification["ok"]:
                    if args.json:
                        _json_dump(report)
                    else:
                        print(
                            "pack signature verification failed: "
                            + "; ".join(verification.get("failures", [])),
                            file=sys.stderr,
                        )
                    return EXIT_FAILURE
            if args.json:
                _json_dump(report)
            else:
                print(f"packed: {zip_path}")
                print(f"sha256: {digest}")
                print(f"pack_hash: {signature.pack_hash}")
                print(f"packer: {signature.packer}")
            return EXIT_OK
        if args.command == "serve":
            import threading

            from .serve import serve_skills

            server, base_url = serve_skills(
                args.skills_dir, host=args.host, port=args.port
            )
            try:
                if args.json:
                    _json_dump(
                        {
                            "ok": True,
                            "url": base_url,
                            "skills_dir": str(args.skills_dir),
                        }
                    )
                else:
                    print(
                        f"serving {args.skills_dir} at {base_url} (Ctrl+C to stop)",
                        flush=True,
                    )
                threading.Event().wait()
            except KeyboardInterrupt:
                pass  # clean foreground shutdown
            finally:
                server.shutdown()
                server.server_close()
            return EXIT_OK
        if args.command == "cache":
            profile = load_profile(args.profile) if args.profile else None
            report = inspect_cache(args.output_dir, profile=profile)
            if args.json:
                _json_dump(report)
            else:
                print(json.dumps(report, indent=2, sort_keys=True))
            return EXIT_OK
        if args.command == "doctor":
            report, exit_code = _doctor(args)
            if args.json:
                _json_dump(report)
            else:
                print("doctor: " + ("ok" if report["ok"] else "failed"))
                for check in report["checks"]:
                    print(f"{'ok' if check.get('ok') else 'FAIL'} {check['name']}")
                if report.get("profiles"):
                    print("profile health:")
                    print(f"  {'status':<6} {'profile':<24} path")
                    for entry in report["profiles"]:
                        label = "ok" if entry.get("ok") else "FAIL"
                        identifier = entry.get("profile_id") or "-"
                        path = entry.get("path") or "-"
                        print(f"  {label:<6} {str(identifier):<24} {path}")
                        if entry.get("error"):
                            print(f"         error: {entry['error']}")
            return exit_code
        if args.command == "evaluate":
            if args.profile:
                for profile_path in args.profile:
                    profile = load_profile(profile_path)
                    parsed = urlparse(profile.base_url)
                    is_local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                    if not args.live and not is_local:
                        raise ValueError(
                            f"public evaluation profile {profile_path} requires --live; "
                            "live acquisition is an explicit opt-in"
                        )
                    run_profile_from_path(
                        profile_path,
                        evidence_origin="fixture" if is_local else "live",
                        output_dir=args.output_dir,
                        backend=args.backend,
                        target_ids=args.targets,
                        refresh=args.refresh,
                        model=args.model,
                        command=args.generator_command,
                        fallback_backend=args.fallback_backend,
                        ollama_model=args.ollama_model,
                        ollama_url=args.ollama_url,
                        ollama_timeout_seconds=args.ollama_timeout,
                        ollama_num_ctx=args.ollama_context,
                        ollama_max_prompt_chars=args.ollama_max_prompt_chars,
                    )
            ratings = _load_rating_files(args.ratings)
            cases_map: dict[tuple[str, str], str] = {}
            if args.cases.exists():
                for case in load_cases(args.cases):
                    cases_map[(case.profile_id, case.target_id)] = case.case_id
            observations = collect_observations(
                args.output_dir,
                source="unknown",
                case_map=cases_map,
                pipeline_version=PIPELINE_VERSION,
            )
            report = build_evaluation_report(observations, ratings=ratings)
            report_path = write_evaluation_report(report, args.output_dir)
            if ratings:
                write_rating_template(
                    args.output_dir / "evaluation" / "ratings-template.csv",
                    sorted({item.case_id for item in report.observations}),
                )
            result = {
                "ok": True,
                "report": str(report_path),
                "summary": report.summary,
                "rating_status": report.rating_status,
            }
            if args.json:
                _json_dump(result)
            else:
                print(report_path)
            return EXIT_OK
        if args.command == "figures":
            report = load_evaluation_report(args.evaluation)
            registry_path = generate_figures(
                report, args.output_dir, source_data=args.evaluation
            )
            result = {
                "ok": True,
                "registry": str(registry_path),
                "validation": validate_figure_registry(registry_path),
            }
            if args.json:
                _json_dump(result)
            else:
                print(registry_path)
            return EXIT_OK if result["validation"]["ok"] else EXIT_FAILURE
        if args.command == "research":
            if args.research_command == "publication":
                manifest_path = write_publication_manifest(
                    args.output_dir,
                    project_root=args.project_root,
                    require_rendered=args.require_rendered,
                )
                validation = validate_publication_manifest(
                    manifest_path,
                    require_rendered=args.require_rendered,
                )
                result = {
                    "ok": validation["ok"],
                    "manifest": str(manifest_path),
                    "validation": validation,
                }
                if args.json:
                    _json_dump(result)
                else:
                    print(manifest_path)
                return EXIT_OK if result["ok"] else EXIT_FAILURE
            if args.research_command == "ratings-template":
                path = write_rating_template(args.output, args.case)
                result = {"ok": True, "ratings_template": str(path)}
                if args.json:
                    _json_dump(result)
                else:
                    print(path)
                return EXIT_OK
            if args.research_command == "build":
                from .publication import build_research_package

                result = build_research_package(
                    args.project_root,
                    args.output_dir,
                    ratings=tuple(args.ratings or ()),
                )
                if args.json:
                    _json_dump(result)
                else:
                    print(
                        f"research inputs: ready; report {result['report_id']}; PDF/HTML rendering pending"
                    )
                return EXIT_OK
            if args.research_command == "manuscript":
                report = load_evaluation_report(args.evaluation)
                validation = validate_manuscript_tree(
                    args.source_dir,
                    figure_registry=args.figures if args.figures.exists() else None,
                )
                rendered = []
                if args.render and validation["ok"]:
                    rendered = [
                        str(path)
                        for path in render_manuscript(
                            args.source_dir,
                            args.output_dir,
                            report,
                            project_root=args.project_root,
                            figure_registry=args.figures
                            if args.figures.exists()
                            else None,
                            site_summaries=load_snapshot_archives(
                                args.output_dir.parent
                            ),
                        )
                    ]
                result = {
                    "ok": validation["ok"],
                    "validation": validation,
                    "rendered": rendered,
                }
                if args.json:
                    _json_dump(result)
                else:
                    print("manuscript: " + ("ok" if result["ok"] else "failed"))
                    for error in validation["errors"]:
                        print(error, file=sys.stderr)
                return EXIT_OK if result["ok"] else EXIT_FAILURE
            citations = load_citations(args.citations)
            claims = load_claims(args.claims)
            observations: set[str] = set()
            if args.evaluation:
                observations = {
                    item.observation_id
                    for item in load_evaluation_report(args.evaluation).observations
                }
            ledger = validate_ledgers(
                citations,
                claims,
                known_observation_ids=observations,
                artifact_root=Path.cwd(),
            )
            if args.bibliography or args.citations == Path("data/citations.yaml"):
                manuscript_check = validate_manuscript_tree(args.manuscript_dir)
                ledger["manuscript_validation"] = manuscript_check
                ledger["ok"] = bool(ledger["ok"] and manuscript_check["ok"])
                bibliography_path = (
                    args.bibliography or args.manuscript_dir / "references.bib"
                )
                bibliography = validate_bibliography(
                    citations,
                    load_bibliography_keys(bibliography_path),
                    extract_manuscript_citations(args.manuscript_dir),
                )
                ledger["bibliography_validation"] = bibliography
                ledger["ok"] = bool(ledger["ok"] and bibliography["ok"])
            else:
                ledger["manuscript_validation"] = {
                    "ok": True,
                    "skipped": True,
                    "reason": (
                        "manuscript and bibliography checks require the default"
                        " citations file or an explicit --bibliography"
                    ),
                }
            if args.adjudication:
                ratings = _load_rating_files(args.ratings)
                if not ratings:
                    ratings_path = args.adjudication.with_name("ratings.csv")
                    ratings = (
                        load_ratings(ratings_path) if ratings_path.exists() else ()
                    )
                adjudication = validate_adjudications(
                    load_adjudications(args.adjudication), ratings
                )
                ledger["adjudication_validation"] = adjudication
                ledger["ok"] = bool(ledger["ok"] and adjudication["ok"])
            elif args.ratings:
                ledger["rating_validation"] = {
                    "ok": True,
                    **review_summary(_load_rating_files(args.ratings)),
                }
            if args.publication.exists():
                publication = validate_publication_manifest(args.publication)
                ledger["publication_validation"] = publication
                ledger["ok"] = bool(ledger["ok"] and publication["ok"])
            figure_result = None
            if args.figures.exists():
                figure_result = validate_figure_registry(args.figures)
                ledger["figure_validation"] = figure_result
                ledger["ok"] = bool(ledger["ok"] and figure_result["ok"])
            if args.json:
                _json_dump(ledger)
            else:
                print("research: " + ("ok" if ledger["ok"] else "failed"))
                for error in ledger["errors"]:
                    print(error, file=sys.stderr)
            return EXIT_OK if ledger["ok"] else EXIT_FAILURE
        results: list[dict[str, Any]] = []
        for path in args.paths:
            try:
                validate_skill_package(path)
                results.append({"path": str(path), "ok": True})
                if not args.json:
                    print(f"valid: {path}")
            except (OSError, ValueError, RuntimeError) as exc:
                results.append({"path": str(path), "ok": False, "error": str(exc)})
                if not args.json:
                    print(f"invalid: {path}: {exc}", file=sys.stderr)
        if args.json:
            _json_dump({"ok": all(item["ok"] for item in results), "results": results})
        return EXIT_OK if all(item["ok"] for item in results) else EXIT_FAILURE
    except httpx.HTTPError as exc:
        if getattr(args, "json", False):
            _json_dump(_error_payload(args, exc))
        else:
            print(f"skillarum: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        if getattr(args, "json", False):
            _json_dump(_error_payload(args, exc))
        else:
            print(f"skillarum: {exc}", file=sys.stderr)
        return EXIT_FAILURE
