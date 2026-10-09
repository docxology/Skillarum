"""Evidence, evaluation, statistics, and publication contracts.

This module is deliberately independent of provider and crawler internals.  It
turns already-persisted Skillarum manifests into auditable observations and
keeps research claims separate from untrusted source-page content.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml

from .manuscript import (
    KNOWN_MANUSCRIPT_TOKENS as KNOWN_MANUSCRIPT_TOKENS,
    MANUSCRIPT_TOKEN_PATTERN as MANUSCRIPT_TOKEN_PATTERN,
    _manuscript_content_paths,
    manuscript_variables as manuscript_variables,
    render_manuscript as render_manuscript,
    validate_manuscript_tree as validate_manuscript_tree,
)
from .models import PreparedCorpus
from .render import validate_skill_package
from .statistics import (
    DEFAULT_POLICY,
    StatisticalPolicy,
    bootstrap_interval,
    exact_binomial_interval,
    numeric_summary,
    ordinal_summary,
    policy_from_mapping,
    policy_payload,
    validate_policy,
    weighted_cohen_kappa,
)
from .utils import (
    is_sha256_hex,
    jsonable,
    provenance_path,
    sha256_bytes,
    sha256_json,
    sha256_text,
    write_bytes_atomic,
    slugify,
    write_json_atomic,
    write_text_atomic,
)

SCHOLARSHIP_SCHEMA_VERSION = 1
PUBLICATION_SCHEMA_VERSION = 1
EvidenceTier = Literal["measured", "live_case", "source", "hypothesis", "pending"]
ClaimStatus = Literal["supported", "hypothesis", "pending"]
ObservationSource = Literal["fixture", "live", "unknown"]
REVIEW_CRITERIA = (
    "semantic_coverage",
    "procedural_usefulness",
    "verification_quality",
    "provenance_fidelity",
    "safety",
    "readability",
)


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _require_nonempty(value: str, label: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{label} must be non-empty, got {value!r}")
    return result


def _is_iso_timestamp(value: str) -> bool:
    if not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class CitationRecord:
    """One bibliography item with an auditable retrieval surface."""

    citation_id: str
    title: str
    authors: tuple[str, ...]
    year: int | None
    kind: str
    url: str
    accessed: str = ""
    doi: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.citation_id, "citation_id")
        _require_nonempty(self.title, "citation title")
        _require_nonempty(self.kind, "citation kind")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"citation url must be absolute http(s), got {self.url!r}")
        if not self.authors or not all(str(author).strip() for author in self.authors):
            raise ValueError(
                "citation authors must contain at least one non-empty author"
            )
        if self.year is not None and not 1900 <= self.year <= 2200:
            raise ValueError(
                f"citation year is outside the supported range, got {self.year!r}"
            )
        if self.accessed:
            try:
                datetime.fromisoformat(self.accessed)
            except ValueError as exc:
                raise ValueError(
                    f"citation accessed date must be ISO-8601, got {self.accessed!r}"
                ) from exc

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "CitationRecord":
        return cls(
            citation_id=_require_nonempty(
                value.get("id", value.get("citation_id", "")), "citation id"
            ),
            title=_require_nonempty(value.get("title", ""), "citation title"),
            authors=_tuple_strings(value.get("authors")),
            year=int(value["year"]) if value.get("year") is not None else None,
            kind=_require_nonempty(value.get("kind", "source"), "citation kind"),
            url=_require_nonempty(value.get("url", ""), "citation url"),
            accessed=str(value.get("accessed", "")),
            doi=str(value["doi"]) if value.get("doi") else None,
            notes=str(value.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ClaimRecord:
    """A manuscript claim and the evidence required before it is publishable."""

    claim_id: str
    text: str
    evidence_tier: EvidenceTier
    status: ClaimStatus
    citation_ids: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.claim_id, "claim_id")
        _require_nonempty(self.text, "claim text")
        if self.evidence_tier not in {
            "measured",
            "live_case",
            "source",
            "hypothesis",
            "pending",
        }:
            raise ValueError(f"unsupported evidence tier {self.evidence_tier!r}")
        if self.status not in {"supported", "hypothesis", "pending"}:
            raise ValueError(f"unsupported claim status {self.status!r}")
        if self.status == "supported" and self.evidence_tier in {
            "hypothesis",
            "pending",
        }:
            raise ValueError("hypothesis or pending evidence cannot support a claim")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ClaimRecord":
        return cls(
            claim_id=_require_nonempty(
                value.get("id", value.get("claim_id", "")), "claim id"
            ),
            text=_require_nonempty(value.get("text", ""), "claim text"),
            evidence_tier=str(value.get("evidence_tier", "pending")),  # type: ignore[arg-type]
            status=str(value.get("status", "pending")),  # type: ignore[arg-type]
            citation_ids=_tuple_strings(
                value.get("citation_ids", value.get("citations"))
            ),
            observation_ids=_tuple_strings(
                value.get("observation_ids", value.get("observations"))
            ),
            artifact_paths=_tuple_strings(
                value.get("artifact_paths", value.get("artifacts"))
            ),
            notes=str(value.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EvaluationCase:
    """One declarative evaluation row, independent of a particular run."""

    case_id: str
    label: str
    profile_id: str
    target_id: str
    source: ObservationSource = "unknown"
    repetitions: int = 1
    notes: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("case_id", self.case_id),
            ("label", self.label),
            ("profile_id", self.profile_id),
            ("target_id", self.target_id),
        ):
            _require_nonempty(value, label)
        if self.repetitions <= 0:
            raise ValueError(
                f"evaluation repetitions must be positive, got {self.repetitions}"
            )
        if self.source not in ("fixture", "live", "unknown"):
            raise ValueError(
                "evaluation case source must be fixture, live, or unknown, "
                f"got {self.source!r}"
            )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "EvaluationCase":
        return cls(
            case_id=_require_nonempty(
                value.get("id", value.get("case_id", "")), "case id"
            ),
            label=_require_nonempty(
                value.get("label", value.get("name", "")), "case label"
            ),
            profile_id=_require_nonempty(
                value.get("profile_id", ""), "case profile_id"
            ),
            target_id=_require_nonempty(value.get("target_id", ""), "case target_id"),
            source=str(value.get("source", "unknown")),  # type: ignore[arg-type]
            repetitions=int(value.get("repetitions", 1)),
            notes=str(value.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EvaluationObservation:
    """One immutable observation derived from a completed run and package."""

    observation_id: str
    case_id: str
    source: ObservationSource
    profile_id: str
    target_id: str
    run_id: str
    observed_at: str
    page_count: int
    request_count: int
    accepted_pages: int
    rejected_requests: int
    redirect_count: int
    canonical_count: int
    duplicate_count: int
    truncated_pages: int
    response_bytes: int
    cache_hits: int
    provider_attempts: int
    provider_failures: int
    retry_count: int
    fallback_used: bool
    selected_backend: str | None
    generator: str
    generation_duration_ms: int
    artifact_sha256: str
    skill_sha256: str
    package_valid: bool
    provenance_complete: bool
    required_sections_valid: bool
    unsafe_source_preserved: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    source_coverage_pages: int = 0
    source_page_total: int = 0
    area: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.observed_at, "observation observed_at")
        for label, value in (
            ("page_count", self.page_count),
            ("request_count", self.request_count),
            ("accepted_pages", self.accepted_pages),
            ("rejected_requests", self.rejected_requests),
            ("redirect_count", self.redirect_count),
            ("canonical_count", self.canonical_count),
            ("duplicate_count", self.duplicate_count),
            ("truncated_pages", self.truncated_pages),
            ("response_bytes", self.response_bytes),
            ("cache_hits", self.cache_hits),
            ("provider_attempts", self.provider_attempts),
            ("provider_failures", self.provider_failures),
            ("retry_count", self.retry_count),
            ("generation_duration_ms", self.generation_duration_ms),
            ("source_coverage_pages", self.source_coverage_pages),
            ("source_page_total", self.source_page_total),
        ):
            if value < 0:
                raise ValueError(
                    f"observation {label} must be non-negative, got {value}"
                )
        if self.source not in ("fixture", "live", "unknown"):
            raise ValueError(
                "observation source must be fixture, live, or unknown, "
                f"got {self.source!r}"
            )
        for label in (
            "fallback_used",
            "package_valid",
            "provenance_complete",
            "required_sections_valid",
            "unsafe_source_preserved",
        ):
            if type(getattr(self, label)) is not bool:
                raise ValueError(
                    f"observation {label} must be a boolean, "
                    f"got {getattr(self, label)!r}"
                )
        if self.source_coverage_pages > self.source_page_total:
            raise ValueError(
                "observation source coverage cannot exceed source page total"
            )
        if not self.artifact_sha256 or not self.skill_sha256:
            raise ValueError("observation artifact and skill hashes are required")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class ReviewRating:
    """One rater's ordinal assessment of a generated skill."""

    case_id: str
    rater_id: str
    semantic_coverage: int
    procedural_usefulness: int
    verification_quality: int
    provenance_fidelity: int
    safety: int
    readability: int
    notes: str = ""
    evidence_urls: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.case_id, "rating case_id")
        _require_nonempty(self.rater_id, "rating rater_id")
        for label in (
            "semantic_coverage",
            "procedural_usefulness",
            "verification_quality",
            "provenance_fidelity",
            "safety",
            "readability",
        ):
            value = getattr(self, label)
            if type(value) is not int or not 0 <= value <= 4:
                raise ValueError(f"{label} must be an integer from 0 to 4, got {value}")
        if any(
            not isinstance(url, str)
            or urlparse(url).scheme not in {"http", "https"}
            or not urlparse(url).netloc
            for url in self.evidence_urls
        ):
            raise ValueError("rating evidence_urls must contain absolute http(s) URLs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class AdjudicationRecord:
    """Auditable resolution of a disagreement between two independent raters."""

    case_id: str
    criterion: str
    rater_ids: tuple[str, ...]
    final_score: int
    adjudicator_id: str
    rationale: str
    evidence_urls: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.case_id, "adjudication case_id")
        _require_nonempty(self.adjudicator_id, "adjudication adjudicator_id")
        if self.criterion not in REVIEW_CRITERIA:
            raise ValueError(f"unsupported review criterion {self.criterion!r}")
        if len(set(self.rater_ids)) < 2:
            raise ValueError("adjudication requires two distinct raters")
        if type(self.final_score) is not int or not 0 <= self.final_score <= 4:
            raise ValueError(
                f"adjudication final_score must be an integer from 0 to 4, got {self.final_score}"
            )
        _require_nonempty(self.rationale, "adjudication rationale")
        if not self.evidence_urls:
            raise ValueError(
                "adjudication requires at least one evidence URL for the final score"
            )
        if any(
            not isinstance(url, str)
            or urlparse(url).scheme not in {"http", "https"}
            or not urlparse(url).netloc
            for url in self.evidence_urls
        ):
            raise ValueError(
                "adjudication evidence_urls must contain absolute http(s) URLs"
            )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AdjudicationRecord":
        return cls(
            case_id=_require_nonempty(value.get("case_id", ""), "adjudication case_id"),
            criterion=_require_nonempty(
                value.get("criterion", ""), "adjudication criterion"
            ),
            rater_ids=_tuple_strings(value.get("rater_ids")),
            final_score=value.get("final_score", -1),
            adjudicator_id=_require_nonempty(
                value.get("adjudicator_id", ""), "adjudication adjudicator_id"
            ),
            rationale=_require_nonempty(
                value.get("rationale", ""), "adjudication rationale"
            ),
            evidence_urls=_tuple_strings(value.get("evidence_urls")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class EvaluationReport:
    """Stable research report envelope consumed by figures and manuscripts."""

    report_id: str
    generated_at: str
    observations: tuple[EvaluationObservation, ...]
    summary: dict[str, Any]
    rating_status: str = "pending"
    schema_version: int = SCHOLARSHIP_SCHEMA_VERSION
    artifact_sha256: str | None = None
    ratings: tuple[ReviewRating, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "observations": [item.to_dict() for item in self.observations],
            "ratings": [item.to_dict() for item in self.ratings],
            "summary": jsonable(self.summary),
            "rating_status": self.rating_status,
            "artifact_sha256": self.artifact_sha256,
        }


def _report_content_hash(report: EvaluationReport) -> str:
    """Hash a report without its self-referential artifact hash."""
    payload = report.to_dict()
    payload.pop("artifact_sha256", None)
    return sha256_json(payload)


def _report_payload_hash(payload: dict[str, Any]) -> str:
    """Hash a serialized report payload without its self-referential digest."""
    content = dict(payload)
    content.pop("artifact_sha256", None)
    return sha256_json(content)


def _event_count(events: list[dict[str, Any]], predicate: Any) -> int:
    return sum(1 for event in events if predicate(event))


def _run_provenance_matches(
    run_path: Path,
    target_record: dict[str, Any],
    skill_manifest: dict[str, Any],
) -> bool | None:
    """Bind a rendered snapshot to the prepared corpus that produced it.

    Schema-1 packages remain readable, but they do not carry enough identity
    fields for this lineage check and therefore return ``None``.  Schema-2
    snapshots must agree with the persisted ``02_prepare`` payload page by
    page.  This prevents a valid-looking package manifest from being promoted
    into research evidence after its source mapping has been altered.
    """
    if skill_manifest.get("schema_version") != 2:
        return None
    target_id = str(target_record.get("target_id", skill_manifest.get("target_id", "")))
    prepared_path = run_path.parent / "02_prepare" / f"{slugify(target_id)}.json"
    try:
        prepared = PreparedCorpus.from_dict(
            json.loads(prepared_path.read_text(encoding="utf-8"))
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return False

    if any(
        str(skill_manifest.get(field, "")) != str(expected)
        for field, expected in (
            ("profile_id", prepared.profile_id),
            ("profile_name", prepared.profile_name),
            ("profile_fingerprint", prepared.profile_fingerprint),
            ("target_id", prepared.target_id),
            ("skill_name", slugify(prepared.skill_name)),
            ("area", prepared.area),
        )
    ):
        return False
    cache_identity = skill_manifest.get("cache_identity")
    if not isinstance(cache_identity, dict) or not is_sha256_hex(
        cache_identity.get("corpus_fingerprint")
    ):
        return False
    allowed_corpus_fingerprints = {
        prepared.fingerprint(),
        prepared.fingerprint(include_retrieval=True),
    }
    if cache_identity.get("corpus_fingerprint") not in allowed_corpus_fingerprints:
        return False
    if skill_manifest.get("requested_skill_name") != prepared.skill_name:
        return False
    source_urls = skill_manifest.get("source_urls")
    pages = skill_manifest.get("pages")
    if source_urls != list(prepared.source_urls) or not isinstance(pages, list):
        return False
    if len(pages) != len(prepared.pages):
        return False

    for package_page, prepared_page in zip(pages, prepared.pages, strict=True):
        if not isinstance(package_page, dict):
            return False
        expected = {
            "url": prepared_page.url,
            "requested_url": prepared_page.requested_url or prepared_page.url,
            "final_url": prepared_page.final_url or prepared_page.url,
            "canonical_url": prepared_page.canonical_url,
            "fetched_at": prepared_page.fetched_at,
            "status_code": prepared_page.status_code,
            "content_sha256": prepared_page.content_sha256
            or sha256_text(prepared_page.text),
            "title": prepared_page.title,
            "truncated": prepared_page.truncated,
            "text_sha256": sha256_text(prepared_page.text),
            "warnings": list(prepared_page.warnings),
        }
        if any(package_page.get(field) != value for field, value in expected.items()):
            return False
    return True


def observation_from_run(
    run_manifest_path: str | Path,
    target_record: dict[str, Any],
    *,
    case_id: str | None = None,
    source: ObservationSource = "unknown",
) -> EvaluationObservation:
    """Build one observation from the existing production manifests."""
    run_path = Path(run_manifest_path)
    run_manifest = json.loads(run_path.read_text(encoding="utf-8"))
    run_id = str(run_manifest.get("run_id", run_path.parent.name))
    reference = target_record.get("package_snapshot") or target_record.get(
        "skill_path", ""
    )
    skill_path = Path(str(reference))
    if not skill_path.is_absolute():
        output_root = run_path.parent.parent.parent
        candidates = (output_root / skill_path, Path.cwd() / skill_path)
        skill_path = next(
            (candidate for candidate in candidates if candidate.exists()), skill_path
        )
    skill_manifest_path = skill_path.parent / "manifest.json"
    package_valid = False
    if skill_path.exists() and skill_manifest_path.exists():
        try:
            # Run snapshots are intentionally stored under stable target
            # slugs, not the user-facing artifact directory name.  Their
            # source-to-run lineage below remains authoritative.
            validate_skill_package(
                skill_path,
                enforce_path_authority=not bool(target_record.get("package_snapshot")),
            )
            package_valid = True
        except (OSError, ValueError, json.JSONDecodeError):
            package_valid = False
    skill_manifest: dict[str, Any] = {}
    manifest_read_error: str | None = None
    if skill_manifest_path.exists():
        try:
            loaded_manifest = json.loads(
                skill_manifest_path.read_text(encoding="utf-8")
            )
            if isinstance(loaded_manifest, dict):
                skill_manifest = loaded_manifest
            else:
                manifest_read_error = "manifest JSON must be an object"
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            manifest_read_error = f"{type(exc).__name__}: {str(exc)[:200]}"
    pages = skill_manifest.get("pages", [])
    events = [
        event
        for event in skill_manifest.get("request_events", [])
        if isinstance(event, dict)
    ]
    trace = skill_manifest.get("generation_trace") or {}
    attempts = [item for item in trace.get("attempts", []) if isinstance(item, dict)]
    accepted = len(pages)
    request_count = int(
        skill_manifest.get(
            "request_count",
            _event_count(events, lambda event: event.get("request_attempt") is True),
        )
    )
    artifact_hash = str(
        (skill_manifest.get("artifact_hashes") or {}).get("SKILL.md", "")
    )
    skill_hash = str(skill_manifest.get("skill_sha256", ""))
    expected_artifact_hash = str(target_record.get("skill_sha256", ""))
    artifact_hash_available = bool(artifact_hash and skill_hash)
    if not artifact_hash:
        artifact_hash = expected_artifact_hash or sha256_text(
            f"unavailable-artifact:{run_id}"
        )
    if not skill_hash:
        skill_hash = artifact_hash
    artifact_reference_matches = (
        not expected_artifact_hash
        or expected_artifact_hash
        in {
            artifact_hash,
            skill_hash,
        }
    )
    if package_valid and not artifact_reference_matches:
        package_valid = False
    source_urls = skill_manifest.get("source_urls", [])
    source_url_set = {str(url) for url in source_urls if str(url).strip()}
    source_coverage_pages = sum(
        1
        for page in pages
        if isinstance(page, dict)
        and str(page.get("url", "")) in source_url_set
        and page.get("content_sha256")
        and page.get("text_sha256")
    )
    provenance_complete = bool(pages) and all(
        isinstance(page, dict)
        and all(
            page.get(field) is not None
            for field in ("url", "final_url", "content_sha256", "text_sha256")
        )
        for page in pages
    )
    run_provenance_match = _run_provenance_matches(
        run_path, target_record, skill_manifest
    )
    if run_provenance_match is not True:
        provenance_complete = False
    metadata = (
        skill_manifest.get("metadata")
        if isinstance(skill_manifest.get("metadata"), dict)
        else {}
    )
    selected_backend = trace.get("selected_backend")
    observation_key = {
        "run_id": run_id,
        "target_id": target_record.get("target_id", skill_manifest.get("target_id")),
        "artifact": artifact_hash or skill_hash,
    }
    observation_id = "obs-" + sha256_json(observation_key)[:20]
    redirects = _event_count(
        events,
        lambda event: (
            event.get("kind") == "redirect" and event.get("status") == "redirect"
        ),
    )
    rejected = _event_count(
        events,
        lambda event: (
            event.get("request_attempt") is True
            and str(event.get("status", "")).startswith("rejected")
        ),
    )
    duplicate_count = _event_count(
        events, lambda event: event.get("kind") == "duplicate"
    )
    canonical_count = sum(
        1 for page in pages if isinstance(page, dict) and page.get("canonical_url")
    )
    response_bytes = sum(int(event.get("bytes", 0) or 0) for event in events)
    generation_duration = sum(int(item.get("duration_ms", 0) or 0) for item in attempts)
    retry_count = sum(int(item.get("retries", 0) or 0) for item in attempts)
    unsafe_source_preserved = "untrusted" in (
        skill_path.read_text(encoding="utf-8").casefold() if skill_path.exists() else ""
    )
    required_sections = False
    if skill_path.exists():
        body = skill_path.read_text(encoding="utf-8").casefold()
        required_sections = all(
            marker in body
            for marker in (
                "## semantic knowledge",
                "## procedural guidance",
                "## verification",
            )
        )
    return EvaluationObservation(
        observation_id=observation_id,
        case_id=case_id
        or str(
            target_record.get("target_id", skill_manifest.get("target_id", "unknown"))
        ),
        source=source,
        profile_id=str(
            run_manifest.get("profile_id", skill_manifest.get("profile_id", ""))
        ),
        target_id=str(
            target_record.get("target_id", skill_manifest.get("target_id", ""))
        ),
        run_id=run_id,
        observed_at=str(
            run_manifest.get("generated_at", skill_manifest.get("run_id", ""))
        ),
        page_count=accepted,
        request_count=request_count,
        accepted_pages=accepted,
        rejected_requests=rejected,
        redirect_count=redirects,
        canonical_count=canonical_count,
        duplicate_count=duplicate_count,
        truncated_pages=sum(
            1 for page in pages if isinstance(page, dict) and page.get("truncated")
        ),
        response_bytes=response_bytes,
        cache_hits=int(bool(target_record.get("acquisition_cache_hit")))
        + int(bool(target_record.get("process_cache_hit"))),
        provider_attempts=len(attempts),
        provider_failures=sum(
            1 for item in attempts if item.get("status") == "failure"
        ),
        retry_count=retry_count,
        fallback_used=bool(trace.get("fallback_used", False)),
        selected_backend=str(selected_backend)
        if selected_backend is not None
        else None,
        generator=str(
            skill_manifest.get("generator", run_manifest.get("generator", "unknown"))
        ),
        generation_duration_ms=generation_duration,
        artifact_sha256=artifact_hash or skill_hash,
        skill_sha256=skill_hash or artifact_hash,
        package_valid=package_valid,
        provenance_complete=provenance_complete,
        required_sections_valid=required_sections,
        unsafe_source_preserved=unsafe_source_preserved
        or bool(metadata.get("untrusted_source")),
        metadata={
            # True when the observation matches a case declared in
            # data/evaluation/cases.yaml rather than an undeclared target.
            "declared_case": case_id is not None,
            "missing_metrics": (
                (
                    ["request_count"]
                    if "request_count" not in skill_manifest and not events
                    else []
                )
                + (["response_bytes"] if not events else [])
                + (
                    [
                        "generation_duration_ms",
                        "provider_attempts",
                        "provider_failures",
                        "retry_count",
                        "fallback_used",
                    ]
                    if not attempts
                    else []
                )
            ),
            "process_cache_hit": bool(target_record.get("process_cache_hit")),
            "acquisition_cache_hit": bool(target_record.get("acquisition_cache_hit")),
            "source_urls": source_urls,
            "warnings": skill_manifest.get("warnings", []),
            "artifact_reference_matches": artifact_reference_matches,
            "package_snapshot": bool(target_record.get("package_snapshot")),
            "run_provenance_match": run_provenance_match,
            "observed_at_valid": _is_iso_timestamp(
                str(run_manifest.get("generated_at", ""))
            ),
            "manifest_read_error": manifest_read_error,
            "artifact_hash_available": artifact_hash_available,
        },
        source_coverage_pages=source_coverage_pages,
        source_page_total=len(pages),
        area=str(run_manifest.get("area", skill_manifest.get("area", ""))),
    )


def collect_observations(
    output_dir: str | Path,
    *,
    source: ObservationSource = "unknown",
    source_by_profile: dict[str, ObservationSource] | None = None,
    case_map: dict[tuple[str, str], str] | None = None,
    pipeline_version: str | None = None,
) -> tuple[EvaluationObservation, ...]:
    """Collect only completed run targets with valid or diagnosable artifacts."""
    root = Path(output_dir)
    candidates: list[tuple[tuple[str, str], Path, dict[str, Any], bool]] = []
    for manifest_path in sorted((root / "runs").glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("state") != "rendered":
            continue
        if (
            pipeline_version is not None
            and manifest.get("pipeline_version") != pipeline_version
        ):
            continue
        for target in manifest.get("target_records", []):
            if not isinstance(target, dict):
                continue
            key = (
                str(manifest.get("profile_id", "")),
                str(target.get("target_id", "")),
            )
            snapshot = target.get("package_snapshot")
            snapshot_exists = False
            if snapshot:
                snapshot_path = Path(str(snapshot))
                if not snapshot_path.is_absolute():
                    snapshot_path = root / snapshot_path
                snapshot_exists = snapshot_path.exists()
            candidates.append((key, manifest_path, target, snapshot_exists))

    snapshot_keys = {key for key, _, _, exists in candidates if exists}
    observations: list[EvaluationObservation] = []
    for key, manifest_path, target, snapshot_exists in candidates:
        # A legacy run points at a mutable top-level skill package. Once a
        # run-specific snapshot exists, omit that legacy pointer rather than
        # silently measuring a later package under the older run ID.
        if key in snapshot_keys and not snapshot_exists:
            continue
        observations.append(
            observation_from_run(
                manifest_path,
                target,
                case_id=(case_map or {}).get(key),
                source=target.get(
                    "evidence_origin", (source_by_profile or {}).get(key[0], source)
                ),
            )
        )
    unique: dict[str, EvaluationObservation] = {}
    for observation in observations:
        previous = unique.get(observation.observation_id)
        if previous is not None and previous.to_dict() != observation.to_dict():
            raise ValueError(
                "conflicting evaluation observations share an observation_id: "
                f"{observation.observation_id}"
            )
        unique[observation.observation_id] = observation
    return tuple(unique[key] for key in sorted(unique))


def _metric_values(
    observations: tuple[EvaluationObservation, ...], field_name: str
) -> list[float]:
    return [
        float(getattr(item, field_name))
        for item in observations
        if field_name not in item.metadata.get("missing_metrics", [])
    ]


def _ordinal_fields(values: list[int]) -> dict[str, Any]:
    """Distribution, mode, and modal share for an ordinal rating sample."""
    return {
        key: value
        for key, value in ordinal_summary(values).items()
        if key not in {"n", "missing"}
    }


def _review_summary_claims_ratings(review: dict[str, Any]) -> bool:
    """True when a stored review summary asserts that rating rows exist."""
    return bool(
        review.get("rating_count", 0)
        or review.get("rater_count", 0)
        or review.get("paired_case_count", 0)
        or review.get("agreement")
        or review.get("raters")
        or review.get("paired_cases")
        or review.get("agreement_undefined")
        or review.get("status") == "complete"
    )


def review_summary(ratings: tuple[ReviewRating, ...]) -> dict[str, Any]:
    """Summarize ratings and gate agreement statistics until two raters exist.

    Agreement is computed only for exactly two distinct rater ids sharing at
    least one case; a third rater keeps the status ``pending`` by design
    rather than silently picking an arbitrary pair to correlate.
    """
    keys = [(rating.case_id, rating.rater_id) for rating in ratings]
    if len(set(keys)) != len(keys):
        raise ValueError("rating case_id and rater_id pairs must be unique")
    raters = sorted({rating.rater_id for rating in ratings})
    criteria = REVIEW_CRITERIA
    paired_cases = (
        sorted(
            set.intersection(
                *[
                    {rating.case_id for rating in ratings if rating.rater_id == rater}
                    for rater in raters[:2]
                ]
            )
        )
        if len(raters) >= 2
        else []
    )
    agreement_status = "complete" if len(raters) == 2 and paired_cases else "pending"
    result: dict[str, Any] = {
        "rating_count": len(ratings),
        "rater_count": len(raters),
        "raters": raters,
        "status": agreement_status,
        "agreement_status": agreement_status,
        "agreement_method": "weighted_cohen_kappa_two_rater"
        if len(raters) == 2
        else "pending_two_rater_workflow",
        "paired_case_count": len(paired_cases),
        "paired_cases": paired_cases,
        "criteria": {
            criterion: {
                **numeric_summary(
                    [float(getattr(rating, criterion)) for rating in ratings],
                    bootstrap=False,
                ),
                **_ordinal_fields(
                    [int(getattr(rating, criterion)) for rating in ratings]
                ),
            }
            for criterion in criteria
        },
        "agreement": {},
        "agreement_undefined": [],
    }
    if agreement_status == "complete":
        for criterion in criteria:
            by_rater = {
                rater: {
                    rating.case_id: int(getattr(rating, criterion))
                    for rating in ratings
                    if rating.rater_id == rater
                }
                for rater in raters[:2]
            }
            kappa = weighted_cohen_kappa(
                by_rater[raters[0]],
                by_rater[raters[1]],
                minimum=DEFAULT_POLICY.rating_minimum,
                maximum=DEFAULT_POLICY.rating_maximum,
            )
            result["agreement"][criterion] = kappa
            if kappa is None:
                result["agreement_undefined"].append(criterion)
    return result


# Summary keys introduced after schema 1 was already publishing.  Report
# loading reconstructs exactly these keys when an older current-format
# report lacks them; every other summary key must match the recomputation.
ADDITIVE_SUMMARY_KEYS = frozenset(
    {
        "run_count",
        "targets_observed_multiple_times",
        "max_observations_per_target",
        "unique_source_url_count",
        "source_url_instance_count",
        "observations_with_complete_telemetry",
    }
)


def summarize_observations(
    observations: tuple[EvaluationObservation, ...],
) -> dict[str, Any]:
    """Aggregate production telemetry for reports and captions.

    Computed exclusively under the canonical ``DEFAULT_POLICY``; the
    embedded policy payload therefore describes exactly what was computed,
    and ``exact_95_interval`` labels are truthful because
    ``DEFAULT_POLICY.confidence`` is 0.95.

    Run/target and page diagnostics distinguish unique runs, unique targets,
    targets observed by more than one run, and unique source URLs from their
    summed instance counts, so overlapping selected runs stay visible
    instead of being silently pooled; no independence between repeated
    observations is implied. ``observations_with_complete_telemetry``
    counts the eligible denominator behind the telemetry-based rates.
    """
    total = len(observations)
    valid = sum(item.package_valid for item in observations)
    fallback_values = _metric_values(observations, "fallback_used")
    fallback = int(sum(fallback_values))
    provenance = sum(item.provenance_complete for item in observations)
    sections = sum(item.required_sections_valid for item in observations)
    unsafe = sum(item.unsafe_source_preserved for item in observations)
    source_coverage_pages = sum(item.source_coverage_pages for item in observations)
    source_page_total = sum(item.source_page_total for item in observations)
    area_groups: dict[str, dict[str, Any]] = {}
    for item in observations:
        area = item.area or item.profile_id
        group = area_groups.setdefault(
            area,
            {
                "observations": 0,
                "targets": set(),
                "accepted_pages": 0,
                "truncated_pages": 0,
                "source_coverage_pages": 0,
                "source_page_total": 0,
            },
        )
        group["observations"] += 1
        group["targets"].add((item.profile_id, item.target_id))
        group["accepted_pages"] += item.accepted_pages
        group["truncated_pages"] += item.truncated_pages
        group["source_coverage_pages"] += item.source_coverage_pages
        group["source_page_total"] += item.source_page_total
    areas = {}
    for area, group in sorted(area_groups.items()):
        total_pages = group["source_page_total"]
        areas[area] = {
            "observation_count": group["observations"],
            "target_count": len(group["targets"]),
            "accepted_pages": group["accepted_pages"],
            "truncated_pages": group["truncated_pages"],
            "source_coverage_pages": group["source_coverage_pages"],
            "source_page_total": total_pages,
            "source_coverage_rate": group["source_coverage_pages"] / total_pages
            if total_pages
            else None,
        }

    def metric(field_name: str) -> dict[str, Any]:
        values = _metric_values(observations, field_name)
        return {**numeric_summary(values), "missing_count": total - len(values)}

    def proportion(successes: int, denominator: int = total) -> dict[str, Any]:
        return {
            "successes": successes,
            "total": denominator,
            "rate": successes / denominator if denominator else None,
            "exact_95_interval": exact_binomial_interval(
                successes, denominator, confidence=DEFAULT_POLICY.confidence
            ),
        }

    metric_names = (
        "page_count",
        "request_count",
        "response_bytes",
        "generation_duration_ms",
    )
    small_sample_metrics = []
    for name in metric_names:
        values = _metric_values(observations, name)
        if values and len(values) < DEFAULT_POLICY.bootstrap_minimum_n:
            small_sample_metrics.append(name)
    small_sample_metrics.sort()
    per_target_counts: dict[tuple[str, str], int] = {}
    source_url_instances = 0
    unique_source_urls: set[str] = set()
    for item in observations:
        target_key = (item.profile_id, item.target_id)
        per_target_counts[target_key] = per_target_counts.get(target_key, 0) + 1
        urls = item.metadata.get("source_urls")
        if isinstance(urls, list):
            cleaned_urls = [str(url) for url in urls if str(url).strip()]
            source_url_instances += len(cleaned_urls)
            unique_source_urls.update(cleaned_urls)
    return {
        "observation_count": total,
        "policy": policy_payload(),
        "small_sample_metrics": small_sample_metrics,
        "profile_count": len({item.profile_id for item in observations}),
        "area_count": len(areas),
        "areas": areas,
        "unique_source_url_count": len(unique_source_urls),
        "source_url_instance_count": source_url_instances,
        "target_count": len(
            {(item.profile_id, item.target_id) for item in observations}
        ),
        "run_count": len({item.run_id for item in observations}),
        "targets_observed_multiple_times": sum(
            1 for count in per_target_counts.values() if count > 1
        ),
        "max_observations_per_target": max(per_target_counts.values(), default=0),
        "package_valid_count": valid,
        "package_valid_rate": valid / total if total else None,
        "fallback_count": fallback,
        "fallback_rate": fallback / len(fallback_values) if fallback_values else None,
        "proportions": {
            "package_valid": proportion(valid),
            "fallback_used": proportion(fallback, len(fallback_values)),
            "provenance_complete": proportion(provenance),
            "required_sections_valid": proportion(sections),
            "unsafe_source_preserved": proportion(unsafe),
            "source_coverage": {
                "successes": source_coverage_pages,
                "total": source_page_total,
                "rate": source_coverage_pages / source_page_total
                if source_page_total
                else None,
                "exact_95_interval": exact_binomial_interval(
                    source_coverage_pages,
                    source_page_total,
                    confidence=DEFAULT_POLICY.confidence,
                ),
            },
        },
        "source_coverage": {
            "pages_with_complete_mapping": source_coverage_pages,
            "pages_observed": source_page_total,
            "rate": source_coverage_pages / source_page_total
            if source_page_total
            else None,
            "missing": source_page_total == 0,
        },
        "page_count": metric("page_count"),
        "request_count": metric("request_count"),
        "response_bytes": metric("response_bytes"),
        "generation_duration_ms": metric("generation_duration_ms"),
        "truncated_pages": sum(item.truncated_pages for item in observations),
        "provider_failures": sum(item.provider_failures for item in observations),
        "retry_count": sum(item.retry_count for item in observations),
        "provenance_complete_count": sum(
            item.provenance_complete for item in observations
        ),
        "required_sections_valid_count": sum(
            item.required_sections_valid for item in observations
        ),
        "unsafe_source_preserved_count": sum(
            item.unsafe_source_preserved for item in observations
        ),
        "request_outcomes": {
            "accepted_pages": sum(item.accepted_pages for item in observations),
            "rejected_requests": sum(item.rejected_requests for item in observations),
            "redirects": sum(item.redirect_count for item in observations),
            "canonicalized_pages": sum(item.canonical_count for item in observations),
            "duplicates": sum(item.duplicate_count for item in observations),
        },
        "telemetry_missing": {
            field: sum(
                field in item.metadata.get("missing_metrics", [])
                for item in observations
            )
            for field in (
                "request_count",
                "response_bytes",
                "generation_duration_ms",
                "provider_attempts",
                "provider_failures",
                "retry_count",
                "fallback_used",
            )
        },
        "observations_with_complete_telemetry": sum(
            not item.metadata.get("missing_metrics") for item in observations
        ),
        "sampling_design": "selected completed run-target snapshots; repeated invocations overwrite stable run identities; intervals require independence assumptions",
        "source_types": {
            source: sum(item.source == source for item in observations)
            for source in ("fixture", "live", "unknown")
        },
    }


def build_evaluation_report(
    observations: tuple[EvaluationObservation, ...],
    *,
    ratings: tuple[ReviewRating, ...] = (),
) -> EvaluationReport:
    payload = [item.to_dict() for item in observations]
    report_id = (
        "evaluation-"
        + sha256_json(
            {"observations": payload, "ratings": [item.to_dict() for item in ratings]}
        )[:20]
    )
    summary = summarize_observations(observations)
    summary["review"] = review_summary(ratings)
    report = EvaluationReport(
        report_id=report_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        observations=observations,
        ratings=ratings,
        summary=summary,
        rating_status=str(summary["review"]["status"]),
    )
    return replace(report, artifact_sha256=_report_content_hash(report))


def load_ratings(path: str | Path) -> tuple[ReviewRating, ...]:
    """Load a CSV rating file, rejecting malformed or out-of-range data.

    Fully blank template rows are skipped; every other malformed row raises
    a ``ValueError`` that names the file row and the offending field so a
    human rater can fix the exact cell.
    """
    result: list[ReviewRating] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            if not any(
                str(row.get(field, "")).strip()
                for field in (
                    "rater_id",
                    "semantic_coverage",
                    "procedural_usefulness",
                    "verification_quality",
                    "provenance_fidelity",
                    "safety",
                    "readability",
                )
            ):
                continue
            case_id = str(row.get("case_id", "")).strip()
            try:
                rating = ReviewRating(
                    case_id=_require_nonempty(row.get("case_id", ""), "rating case_id"),
                    rater_id=_require_nonempty(
                        row.get("rater_id", ""), "rating rater_id"
                    ),
                    semantic_coverage=int(row.get("semantic_coverage", "")),
                    procedural_usefulness=int(row.get("procedural_usefulness", "")),
                    verification_quality=int(row.get("verification_quality", "")),
                    provenance_fidelity=int(row.get("provenance_fidelity", "")),
                    safety=int(row.get("safety", "")),
                    readability=int(row.get("readability", "")),
                    notes=str(row.get("notes", "")),
                    evidence_urls=tuple(
                        item.strip()
                        for item in str(row.get("evidence_urls", "")).split(",")
                        if item.strip()
                    ),
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{Path(path)} row {row_number} "
                    f"(case_id={case_id or 'missing'}): {exc}"
                ) from exc
            if not rating.notes.strip() and not rating.evidence_urls:
                raise ValueError(
                    f"{Path(path)} row {row_number} "
                    f"(case_id={rating.case_id}/{rating.rater_id}): rating "
                    f"requires evidence notes or URLs"
                )
            result.append(rating)
    keys = [(rating.case_id, rating.rater_id) for rating in result]
    if len(set(keys)) != len(keys):
        raise ValueError("rating case_id and rater_id pairs must be unique")
    return tuple(result)


def load_adjudications(path: str | Path) -> tuple[AdjudicationRecord, ...]:
    """Load JSON adjudication records without treating absence as data."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    items = value.get("adjudications", value) if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError("adjudication file must contain a list")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("adjudication entries must all be mappings")
    records = tuple(AdjudicationRecord.from_mapping(item) for item in items)
    keys = [(item.case_id, item.criterion) for item in records]
    if len(set(keys)) != len(keys):
        raise ValueError("adjudication case and criterion pairs must be unique")
    return records


def validate_adjudications(
    records: tuple[AdjudicationRecord, ...], ratings: tuple[ReviewRating, ...]
) -> dict[str, Any]:
    """Check that adjudications refer to two actual rating rows.

    Adjudications that restate an existing agreement — both raters already
    scored the criterion identically — are reported separately as
    ``adjudications_without_disagreement``.  They are not errors, but they
    do not evidence disagreement resolution.
    """
    rows = {(rating.case_id, rating.rater_id): rating for rating in ratings}
    errors: list[str] = []
    without_disagreement: list[str] = []
    for record in records:
        missing = sorted(
            f"{record.case_id}:{rater}"
            for rater in record.rater_ids
            if (record.case_id, rater) not in rows
        )
        if missing:
            errors.append(
                f"{record.case_id}/{record.criterion}: missing rating rows {missing}"
            )
            continue
        first, second = (
            rows[(record.case_id, rater)] for rater in record.rater_ids[:2]
        )
        if getattr(first, record.criterion) == getattr(second, record.criterion):
            without_disagreement.append(f"{record.case_id}/{record.criterion}")
    return {
        "ok": not errors,
        "status": "complete" if records and not errors else "pending",
        "adjudication_count": len(records),
        "adjudications_without_disagreement": without_disagreement,
        "errors": errors,
    }


def write_rating_template(path: str | Path, case_ids: list[str]) -> Path:
    """Write a blank, reviewable rating template without inventing scores.

    Case ids must be CSV-safe: a comma, quote, or newline inside a case id
    would corrupt the template's column structure, so such ids are rejected
    instead of silently quoted.
    """
    destination = Path(path)
    for case_id in case_ids:
        if not str(case_id).strip():
            raise ValueError("rating template case ids must be non-empty")
        if any(character in str(case_id) for character in (",", '"', "\n", "\r")):
            raise ValueError(
                "rating template case ids must not contain commas, quotes, "
                f"or newlines, got {case_id!r}"
            )
    rows = [
        "case_id,rater_id,semantic_coverage,procedural_usefulness,verification_quality,provenance_fidelity,safety,readability,notes,evidence_urls"
    ]
    rows.extend(f"{case_id},,,,,,,,," for case_id in case_ids)
    write_text_atomic(destination, "\n".join(rows) + "\n")
    return destination


def load_citations(path: str | Path) -> tuple[CitationRecord, ...]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = value.get("citations", value) if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError(
            f"citation ledger must contain a list, got {type(items).__name__}"
        )
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("citation ledger entries must all be mappings")
    raw_ids = [
        str(item.get("id", item.get("citation_id", ""))).strip() for item in items
    ]
    if len(set(raw_ids)) != len(raw_ids):
        raise ValueError("citation ids must be unique")
    citations = tuple(CitationRecord.from_mapping(item) for item in items)
    if len({item.citation_id for item in citations}) != len(citations):
        raise ValueError("citation ids must be unique")
    return citations


def load_claims(path: str | Path) -> tuple[ClaimRecord, ...]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = value.get("claims", value) if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError(
            f"claim ledger must contain a list, got {type(items).__name__}"
        )
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("claim ledger entries must all be mappings")
    raw_ids = [str(item.get("id", item.get("claim_id", ""))).strip() for item in items]
    if len(set(raw_ids)) != len(raw_ids):
        raise ValueError("claim ids must be unique")
    claims = tuple(ClaimRecord.from_mapping(item) for item in items)
    if len({item.claim_id for item in claims}) != len(claims):
        raise ValueError("claim ids must be unique")
    return claims


def load_cases(path: str | Path) -> tuple[EvaluationCase, ...]:
    """Load the declarative live-matrix plan that names observed profile/target pairs.

    The plan does not claim a run occurred; it binds a stable case id (and an
    intended evidence-tier label) to a ``(profile_id, target_id)`` key.  The
    evaluation CLI uses this mapping so measurement is attributable to the
    declared study matrix instead of drifting with run-manifest keys.
    """
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = value.get("cases", value) if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ValueError(
            f"evaluation case file must contain a list, got {type(items).__name__}"
        )
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("evaluation case entries must all be mappings")
    cases = tuple(EvaluationCase.from_mapping(item) for item in items)
    keys = [(case.case_id, case.profile_id, case.target_id) for case in cases]
    if len(set(keys)) != len(keys):
        raise ValueError("evaluation case ids must be unique per profile-target")
    return cases


def validate_ledgers(
    citations: tuple[CitationRecord, ...],
    claims: tuple[ClaimRecord, ...],
    *,
    known_observation_ids: set[str] | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate cross-references and reject unsupported artifact evidence.

    Artifact references are project-relative evidence paths.  They are checked
    for traversal/private-state escapes in every call; when ``artifact_root``
    is supplied, they must also resolve to regular files.  This keeps a claim
    ledger from treating a merely named, missing, or private cache path as
    evidence while retaining backward-compatible validation for callers that
    only have the ledger objects.
    """
    citation_ids = {item.citation_id for item in citations}
    observation_ids = known_observation_ids or set()
    root = Path(artifact_root).resolve() if artifact_root is not None else None
    errors: list[str] = []
    for claim in claims:
        missing_citations = sorted(set(claim.citation_ids) - citation_ids)
        missing_observations = sorted(set(claim.observation_ids) - observation_ids)
        if missing_citations:
            errors.append(f"{claim.claim_id}: missing citations {missing_citations}")
        if missing_observations:
            errors.append(
                f"{claim.claim_id}: missing observations {missing_observations}"
            )
        for reference in claim.artifact_paths:
            relative = Path(reference)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or any(part.casefold() in {".cache", "runs"} for part in relative.parts)
            ):
                errors.append(f"{claim.claim_id}: unsafe artifact path {reference!r}")
                continue
            if root is not None:
                artifact = root / relative
                try:
                    artifact.resolve(strict=True).relative_to(root)
                except (OSError, ValueError):
                    errors.append(
                        f"{claim.claim_id}: artifact path is missing or escapes root: {reference}"
                    )
                else:
                    if not artifact.is_file() or artifact.is_symlink():
                        errors.append(
                            f"{claim.claim_id}: artifact path is not a regular file: {reference}"
                        )
        if claim.status == "supported" and not (
            claim.citation_ids or claim.observation_ids or claim.artifact_paths
        ):
            errors.append(
                f"{claim.claim_id}: supported claim has no evidence reference"
            )
    return {
        "schema_version": SCHOLARSHIP_SCHEMA_VERSION,
        "ok": not errors,
        "citation_count": len(citations),
        "claim_count": len(claims),
        "errors": errors,
    }


def load_bibliography_keys(path: str | Path) -> set[str]:
    """Read BibTeX entry keys with a small parser suitable for validation."""
    text = Path(path).read_text(encoding="utf-8")
    return set(re.findall(r"(?im)^\s*@[^\{]+\{\s*([^,\s]+)", text))


def extract_manuscript_citations(source_dir: str | Path) -> set[str]:
    """Extract Pandoc-style citation keys from Markdown sources.

    Structural cross-reference prefixes (``fig``, ``sec``, ``eq``, ``tbl``,
    ``def``, ``prop``) resolve as internal pandoc-crossref links, not
    bibliography keys, and are excluded.
    """
    structural_prefixes = ("fig", "sec", "eq", "tbl", "def", "prop")
    keys: set[str] = set()
    for path in _manuscript_content_paths(Path(source_dir)):
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r"(?<![A-Za-z0-9_/])@([A-Za-z][A-Za-z0-9:_-]*)", text):
            if ":" in key and key.split(":", 1)[0] in structural_prefixes:
                continue
            keys.add(key)
    return keys


def validate_bibliography(
    citations: tuple[CitationRecord, ...],
    bibliography_keys: set[str],
    manuscript_citations: set[str],
) -> dict[str, Any]:
    """Ensure ledger records and manuscript citations resolve to BibTeX keys."""
    errors = [
        f"ledger citation missing from bibliography: {item.citation_id}"
        for item in citations
        if item.citation_id not in bibliography_keys
    ]
    errors.extend(
        f"manuscript citation missing from bibliography: {key}"
        for key in sorted(manuscript_citations - bibliography_keys)
    )
    return {
        "ok": not errors,
        "bibliography_count": len(bibliography_keys),
        "manuscript_citation_count": len(manuscript_citations),
        "errors": errors,
    }


def _resolve_output_reference(root: Path, reference: str) -> Path:
    """Resolve an evaluation-manifest path while accepting old ``output/...`` references."""
    candidate = Path(reference)
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] == root.name:
        candidate = Path(*candidate.parts[1:])
    return root / candidate


def _current_evaluation_artifacts(root: Path) -> tuple[set[Path], list[str]]:
    """Select the one integrity-checked evaluation report for publication.

    Older output trees may predate ``evaluation-manifest.json``.  In that
    case, retain backward-readable behavior and include all snapshots while
    making the weaker selection explicit in the publication manifest.
    """
    manifest_path = root / "reports" / "evaluation-manifest.json"
    if not manifest_path.exists():
        return set(root.glob("evaluation/*.json")), [
            "canonical evaluation manifest unavailable; retained all evaluation snapshots"
        ]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"evaluation manifest is unreadable: {manifest_path}") from exc
    if manifest.get("schema_version") != SCHOLARSHIP_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported evaluation manifest schema: {manifest.get('schema_version')!r}"
        )
    try:
        report_path = _resolve_output_reference(root, str(manifest["report_file"]))
        summary_path = _resolve_output_reference(root, str(manifest["summary_file"]))
        expected_report_hash = str(manifest["report_sha256"])
        expected_summary_hash = str(manifest["summary_sha256"])
        report_id = str(manifest["report_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"evaluation manifest lacks canonical report references: {manifest_path}"
        ) from exc
    root_resolved = root.resolve()
    paths = (report_path, summary_path, manifest_path)
    for path in paths:
        try:
            path.resolve(strict=True).relative_to(root_resolved)
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError(
                f"evaluation manifest references a path outside output: {path}"
            ) from exc
        if path.is_symlink() or not path.is_file():
            raise ValueError(
                f"evaluation manifest references a non-regular file: {path}"
            )
    try:
        report_relative = report_path.resolve(strict=True).relative_to(root_resolved)
        summary_relative = summary_path.resolve(strict=True).relative_to(root_resolved)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(
            "evaluation manifest references an invalid canonical report path"
        ) from exc
    if (
        report_relative.parts[:1] != ("evaluation",)
        or report_relative.name != f"{report_id}.json"
    ):
        raise ValueError(
            "canonical evaluation report must be evaluation/<report_id>.json"
        )
    if summary_relative != Path("reports/evaluation-summary.json"):
        raise ValueError(
            "canonical evaluation summary must be reports/evaluation-summary.json"
        )
    if not is_sha256_hex(expected_report_hash) or not is_sha256_hex(
        expected_summary_hash
    ):
        raise ValueError(
            "evaluation manifest report hash and summary hash values must be SHA-256 hex digests"
        )
    if sha256_bytes(report_path.read_bytes()) != expected_report_hash:
        raise ValueError(f"canonical evaluation report hash mismatch: {report_path}")
    if sha256_bytes(summary_path.read_bytes()) != expected_summary_hash:
        raise ValueError(f"canonical evaluation summary hash mismatch: {summary_path}")
    if report_path.read_bytes() != summary_path.read_bytes():
        raise ValueError(
            "canonical evaluation report and summary must be byte-identical"
        )
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    if report_payload.get("report_id") != report_id:
        raise ValueError(
            "evaluation manifest report_id does not match canonical report"
        )
    if report_payload.get("schema_version") != SCHOLARSHIP_SCHEMA_VERSION:
        raise ValueError("canonical evaluation report schema does not match manifest")
    if report_payload.get("artifact_sha256") != _report_payload_hash(report_payload):
        raise ValueError("canonical evaluation report self-hash mismatch")
    return set(paths), [
        "stale evaluation snapshots excluded; evaluation-manifest.json selects the canonical report"
    ]


def _project_manuscript_config(project_root: Path) -> Path | None:
    """Locate the project's manuscript config.yaml, docs/manuscript/ first.

    ``docs/manuscript/`` is the canonical location; the legacy top-level
    ``manuscript/`` directory is kept as a fallback so checkouts mid-migration
    (and older project roots) keep resolving.
    """
    for candidate in (
        project_root / "docs" / "manuscript" / "config.yaml",
        project_root / "manuscript" / "config.yaml",
    ):
        if candidate.is_file():
            return candidate
    return None


def _materialize_publication_metadata(root: Path, project_root: Path | None) -> None:
    """Copy auditable project metadata into the output publication surface."""
    if project_root is None:
        return
    destination = root / "manuscript" / "provenance"
    manuscript_config = _project_manuscript_config(project_root)
    for relative in (
        "CITATION.cff",
        "data/citations.yaml",
        "data/claims.yaml",
        "data/cover.yaml",
    ):
        source = project_root / relative
        if source.is_file():
            write_text_atomic(
                destination / Path(relative).name, source.read_text(encoding="utf-8")
            )
    if manuscript_config is not None:
        write_text_atomic(
            destination / "config.yaml", manuscript_config.read_text(encoding="utf-8")
        )
    cover = project_root / "cover" / "skillarum_cover.png"
    if cover.is_file():
        write_bytes_atomic(
            root / "manuscript" / "skillarum_cover.png", cover.read_bytes()
        )


def _publication_artifact_paths(root: Path) -> tuple[Path, ...]:
    """Return an explicit, reviewable publication allowlist.

    Runtime guidance files are intentionally excluded.  The current evaluation
    snapshot is selected by its integrity manifest so repeated local runs do
    not accidentally publish contradictory historical reports.
    """
    evaluation_paths, _ = _current_evaluation_artifacts(root)
    patterns = (
        "skills/index.json",
        "skills/**/SKILL.md",
        "skills/**/manifest.json",
        "figures/*.svg",
        "figures/*.png",
        "figures/*.json",
        "figures/figure_data/*.json",
        "data/manuscript_variables.json",
        "data/manuscript_bindings.json",
        "reports/evaluation-manifest.json",
        "reports/evaluation-summary.json",
        "manuscript/[0-9][0-9]_*.md",
        "manuscript/preamble.md",
        "manuscript/*.yaml",
        "manuscript/*.bib",
        "manuscript/*.png",
        "manuscript/provenance/*",
        "pdf/*.pdf",
        "web/*.html",
        "web/*.ico",
    )
    return tuple(
        sorted(
            {
                path
                for pattern in patterns
                for path in root.glob(pattern)
                if (path.is_file() or path.is_symlink())
                and path.name != "publication-manifest.json"
            }
            | {
                path
                for path in evaluation_paths
                if (path.is_file() or path.is_symlink())
                and path.name != "publication-manifest.json"
            }
        )
    )


def write_publication_manifest(
    output_dir: str | Path,
    *,
    project_root: str | Path | None = None,
    require_rendered: bool = False,
) -> Path:
    """Hash publication outputs while excluding caches, runs, logs, and secrets."""
    root = Path(output_dir)
    _materialize_publication_metadata(
        root, Path(project_root) if project_root is not None else None
    )
    artifacts = _publication_artifact_paths(root)
    forbidden_markers = (
        re.compile(rb"OPENAI_API_KEY"),
        re.compile(rb"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
        re.compile(rb"sk-(?:proj|live|test)-[A-Za-z0-9_-]{16,}"),
    )
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for path in artifacts:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f"symlink is not publishable: {relative}")
            continue
        if any(
            part.casefold() in {".cache", "runs"}
            for part in path.relative_to(root).parts
        ):
            errors.append(f"private runtime path selected for publication: {relative}")
        content = path.read_bytes()
        if any(marker.search(content) for marker in forbidden_markers):
            errors.append(
                f"credential marker found in publication artifact: {relative}"
            )
        hashes[relative] = sha256_bytes(content)
    if errors:
        raise ValueError("publication boundary validation failed: " + "; ".join(errors))
    render_requirements = {
        "pdf": (root / "pdf").glob("*.pdf"),
        "html": (root / "web").glob("*.html"),
    }
    rendered_counts = {
        format_name: len(tuple(paths))
        for format_name, paths in render_requirements.items()
    }
    if require_rendered and any(count == 0 for count in rendered_counts.values()):
        raise ValueError(
            f"configured publication formats are missing: {rendered_counts}"
        )
    manifest = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "artifact_count": len(hashes),
        "artifact_hashes": hashes,
        "excluded": [
            "output/.cache",
            "output/runs",
            "credentials and authorization headers",
            "stale evaluation snapshots (the current evaluation manifest is authoritative)",
            "manuscript/AGENTS.md",
            "manuscript/README.md",
        ],
        "selection": "explicit allowlist plus the integrity-checked canonical evaluation report",
        "project_root": provenance_path(Path(project_root))
        if project_root is not None
        else None,
        "rendered_counts": rendered_counts,
        "render_requirement": "pdf and html required"
        if require_rendered
        else "optional until parent-template rendering",
    }
    destination = root / "reports" / "publication-manifest.json"
    write_json_atomic(destination, manifest)
    return destination


def validate_publication_manifest(
    path: str | Path, *, require_rendered: bool = False
) -> dict[str, Any]:
    """Validate each listed publication artifact and its exclusion boundary."""
    manifest_path = Path(path)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value.get("schema_version") != PUBLICATION_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported publication schema: {value.get('schema_version')!r}"
        )
    root = manifest_path.parent.parent
    errors: list[str] = []
    hashes = value.get("artifact_hashes", {})
    if not isinstance(hashes, dict):
        raise ValueError("publication artifact_hashes must be a mapping")
    for relative, expected in hashes.items():
        relative_path = Path(str(relative))
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or any(
                part.casefold() in {".cache", "runs"} for part in relative_path.parts
            )
        ):
            errors.append(f"forbidden publication path: {relative}")
            continue
        artifact = root / relative_path
        if artifact.is_symlink():
            errors.append(f"symlink is not a publishable artifact: {relative}")
            continue
        if not artifact.is_file():
            errors.append(f"missing publication artifact: {relative}")
            continue
        try:
            artifact.resolve(strict=True).relative_to(root.resolve())
        except ValueError:
            errors.append(f"publication artifact escapes output root: {relative}")
            continue
        actual = sha256_bytes(artifact.read_bytes())
        if actual != expected:
            errors.append(f"publication artifact hash mismatch: {relative}")
    if value.get("artifact_count") != len(hashes):
        errors.append("publication artifact_count does not match artifact_hashes")
    actual_counts = {
        name: sum(
            Path(relative).parent == Path(folder) and Path(relative).suffix == suffix
            for relative in hashes
        )
        for name, folder, suffix in (("pdf", "pdf", ".pdf"), ("html", "web", ".html"))
    }
    declared_counts = value.get("rendered_counts", {})
    if "rendered_counts" in value and declared_counts != actual_counts:
        errors.append("publication rendered_counts do not match listed artifacts")
    if require_rendered and any(count == 0 for count in actual_counts.values()):
        errors.append("publication manifest lacks required PDF and HTML artifacts")
    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "ok": not errors,
        "artifact_count": len(hashes),
        "errors": errors,
    }


def write_evaluation_report(report: EvaluationReport, output_dir: str | Path) -> Path:
    """Publish a report and an integrity manifest using atomic writes."""
    if report.artifact_sha256 != _report_content_hash(report):
        report = replace(report, artifact_sha256=_report_content_hash(report))
    destination = Path(output_dir) / "evaluation" / f"{report.report_id}.json"
    write_json_atomic(destination, report.to_dict())
    summary_path = Path(output_dir) / "reports" / "evaluation-summary.json"
    write_json_atomic(summary_path, report.to_dict())
    manifest_path = Path(output_dir) / "reports" / "evaluation-manifest.json"
    manifest = {
        "schema_version": SCHOLARSHIP_SCHEMA_VERSION,
        "report_id": report.report_id,
        "report_content_sha256": report.artifact_sha256,
        "report_file": destination.relative_to(Path(output_dir)).as_posix(),
        "report_sha256": sha256_bytes(destination.read_bytes()),
        "summary_file": summary_path.relative_to(Path(output_dir)).as_posix(),
        "summary_sha256": sha256_bytes(summary_path.read_bytes()),
    }
    write_json_atomic(manifest_path, manifest)
    return destination


def load_evaluation_report(path: str | Path) -> EvaluationReport:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != SCHOLARSHIP_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported evaluation schema: {value.get('schema_version')!r}"
        )
    artifact_sha256 = value.get("artifact_sha256")
    if artifact_sha256:
        payload = dict(value)
        payload.pop("artifact_sha256", None)
        expected = sha256_json(payload)
        if artifact_sha256 != expected:
            raise ValueError(f"evaluation artifact hash does not match: {path}")
    try:
        observations = tuple(
            EvaluationObservation(**item) for item in value.get("observations", [])
        )
        ratings = tuple(
            ReviewRating(
                **{**item, "evidence_urls": tuple(item.get("evidence_urls", ()) or ())}
            )
            for item in value.get("ratings", [])
        )
    except TypeError as exc:
        raise ValueError(f"evaluation report records are malformed: {exc}") from exc
    summary = dict(value.get("summary", {}))
    recomputed = summarize_observations(observations)
    migrated = False
    legacy_payload = "ratings" not in value
    if legacy_payload:
        # Reports written before rating rows were persisted stay readable:
        # stored keys are verified and missing keys are reconstructed from
        # the observations rather than defaulted to zeros.
        for key, expected in recomputed.items():
            if key in summary and jsonable(summary[key]) != jsonable(expected):
                raise ValueError(
                    f"evaluation summary disagrees with observations: {key}"
                )
            summary.setdefault(key, expected)
    else:
        missing = sorted(key for key in recomputed if key not in summary)
        unexpected = sorted(set(missing) - ADDITIVE_SUMMARY_KEYS)
        if unexpected:
            raise ValueError(f"evaluation summary is missing keys: {missing}")
        for key in missing:
            # Additive diagnostics introduced after this report was written
            # are reconstructed from the observations; nothing is invented.
            summary[key] = recomputed[key]
            migrated = True
        for key, expected in recomputed.items():
            if jsonable(summary[key]) != jsonable(expected):
                raise ValueError(
                    f"evaluation summary disagrees with observations: {key}"
                )
    stored_review = summary.get("review")
    if not ratings and (
        str(value.get("rating_status", "pending")) == "complete"
        or (
            isinstance(stored_review, dict)
            and _review_summary_claims_ratings(stored_review)
        )
    ):
        raise ValueError(
            "evaluation summary claims review statistics without rating rows"
        )
    recomputed_review = review_summary(ratings)
    if str(value.get("rating_status", "pending")) != str(recomputed_review["status"]):
        raise ValueError(
            "evaluation rating_status disagrees with rederived review status"
        )
    if legacy_payload:
        if isinstance(stored_review, dict):
            for key, expected in recomputed_review.items():
                if key in stored_review and jsonable(stored_review[key]) != jsonable(
                    expected
                ):
                    raise ValueError(
                        f"evaluation review summary disagrees with rating rows: {key}"
                    )
                stored_review.setdefault(key, expected)
        else:
            stored_review = dict(recomputed_review)
        summary["review"] = stored_review
    else:
        if not isinstance(stored_review, dict):
            raise ValueError("current evaluation reports require a review summary")
        missing_review = sorted(
            key for key in recomputed_review if key not in stored_review
        )
        if missing_review:
            raise ValueError(
                f"evaluation review summary is missing keys: {missing_review}"
            )
        for key, expected in recomputed_review.items():
            if jsonable(stored_review[key]) != jsonable(expected):
                raise ValueError(
                    f"evaluation review summary disagrees with rating rows: {key}"
                )
    report = EvaluationReport(
        report_id=str(value["report_id"]),
        generated_at=str(value.get("generated_at", "")),
        observations=observations,
        ratings=ratings,
        summary=summary,
        rating_status=str(value.get("rating_status", "pending")),
        artifact_sha256=str(artifact_sha256) if artifact_sha256 else None,
    )
    if legacy_payload or migrated:
        # Reconstruction changed the content: rederive the digest explicitly
        # so the loaded envelope is self-consistent.
        return replace(report, artifact_sha256=_report_content_hash(report))
    return report


__all__ = [
    "DEFAULT_POLICY",
    "StatisticalPolicy",
    "SCHOLARSHIP_SCHEMA_VERSION",
    "PUBLICATION_SCHEMA_VERSION",
    "CitationRecord",
    "ClaimRecord",
    "AdjudicationRecord",
    "EvaluationCase",
    "EvaluationObservation",
    "EvaluationReport",
    "ReviewRating",
    "bootstrap_interval",
    "build_evaluation_report",
    "collect_observations",
    "exact_binomial_interval",
    "load_claims",
    "load_citations",
    "load_cases",
    "load_adjudications",
    "load_bibliography_keys",
    "load_evaluation_report",
    "load_ratings",
    "manuscript_variables",
    "numeric_summary",
    "ordinal_summary",
    "policy_from_mapping",
    "policy_payload",
    "validate_policy",
    "observation_from_run",
    "review_summary",
    "render_manuscript",
    "summarize_observations",
    "validate_manuscript_tree",
    "validate_ledgers",
    "validate_adjudications",
    "validate_bibliography",
    "write_publication_manifest",
    "validate_publication_manifest",
    "extract_manuscript_citations",
    "weighted_cohen_kappa",
    "write_evaluation_report",
    "write_rating_template",
]
