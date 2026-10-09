"""Filesystem-backed acquire/prepare/process/parse/render orchestration."""

from __future__ import annotations

import binascii
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .config import load_profile
from .crawler import ConditionalEntry, WebsiteCrawler
from .generators import (
    SkillGenerator,
    _sanitize_error,
    generator_for,
    validate_generated_body,
)
from .models import (
    BundleRecord,
    GenerationAttempt,
    GenerationConfig,
    GenerationTrace,
    SkillDraft,
    SourceProfile,
    TargetSpec,
)
from .prepare import prepare_corpus
from .render import render_skill, write_skill_index
from .utils import (
    artifact_name,
    interprocess_lock,
    sha256_json,
    sha256_text,
    slugify,
    write_bytes_atomic,
    write_json_atomic,
)


# Version persisted stage contracts so old runs/caches cannot be mistaken for
# artifacts produced under current verifier and security semantics.
PIPELINE_VERSION = "0.8"
CACHE_VERSION = 7


def _write_json(path: Path, value: object) -> None:
    """Persist a stage artifact deterministically and atomically."""
    write_json_atomic(path, value)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _bundle_cache_path(
    cache_root: Path, profile: SourceProfile, target: TargetSpec
) -> Path:
    return (
        cache_root
        / "bundles"
        / f"{slugify(profile.id)}--{slugify(target.id)}--{profile.fingerprint()[:20]}.json"
    )


def _cached_bundle(
    path: Path,
    *,
    profile_fingerprint: str,
    target_id: str,
    target_fingerprint: str,
) -> BundleRecord | None:
    if not path.exists() or path.is_symlink():
        return None
    try:
        payload = _read_json(path)
        if (
            payload.get("cache_version") != CACHE_VERSION
            or payload.get("pipeline_version") != PIPELINE_VERSION
            or payload.get("profile_fingerprint") != profile_fingerprint
            or payload.get("target_id") != target_id
            or payload.get("target_fingerprint") != target_fingerprint
        ):
            return None
        bundle_payload = payload["bundle"]
        if payload.get("bundle_sha256") != sha256_json(bundle_payload):
            return None
        return BundleRecord.from_dict(bundle_payload)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _write_bundle_cache(
    path: Path,
    bundle: BundleRecord,
    *,
    profile_fingerprint: str,
    target_id: str,
    target_fingerprint: str,
) -> None:
    bundle_payload = bundle.to_dict()
    _write_json(
        path,
        {
            "pipeline_version": PIPELINE_VERSION,
            "cache_version": CACHE_VERSION,
            "profile_fingerprint": profile_fingerprint,
            "target_id": target_id,
            "target_fingerprint": target_fingerprint,
            "bundle_sha256": sha256_json(bundle_payload),
            "bundle": bundle_payload,
        },
    )


_LATENCY_BUCKETS_MS: tuple[tuple[str, int], ...] = (
    ("lt_100ms", 100),
    ("100_300ms", 300),
    ("300_1000ms", 1_000),
    ("1000_3000ms", 3_000),
)

_TIMEOUT_MARKERS = (
    "timeout",
    "connecttimeout",
    "readtimeout",
    "writetimeout",
    "pooltimeout",
)


def _latency_histogram(durations_ms: list[int]) -> dict[str, Any]:
    """Bucketed latency histogram plus quantiles for one domain."""
    buckets = {name: 0 for name, _ in _LATENCY_BUCKETS_MS}
    buckets["gte_3000ms"] = 0
    for duration in durations_ms:
        for name, upper in _LATENCY_BUCKETS_MS:
            if duration < upper:
                buckets[name] += 1
                break
        else:
            buckets["gte_3000ms"] += 1
    ordered = sorted(durations_ms)
    count = len(ordered)

    def quantile(fraction: float) -> int:
        if not ordered:
            return 0
        index = min(count - 1, int(round(fraction * (count - 1))))
        return ordered[index]

    return {
        "count": count,
        "min_ms": ordered[0] if ordered else 0,
        "max_ms": ordered[-1] if ordered else 0,
        "mean_ms": round(sum(ordered) / count) if ordered else 0,
        "p50_ms": quantile(0.50),
        "p95_ms": quantile(0.95),
        "buckets": buckets,
    }


def acquisition_metrics(
    events: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate retry-budget metrics from acquisition request events.

    Extends the per-target ``request_events`` with run-level totals: request
    counts, retry counts, timeout counts, and a per-domain latency histogram.
    """
    requests = 0
    retries = 0
    timeouts = 0
    domain_durations: dict[str, list[int]] = {}
    for event in events:
        if not isinstance(event, Mapping):
            continue
        if event.get("request_attempt"):
            requests += 1
        if event.get("status") == "retrying":
            retries += 1
        reason = str(event.get("reason", "")).lower()
        if reason and any(marker in reason for marker in _TIMEOUT_MARKERS):
            timeouts += 1
        url = str(event.get("url", ""))
        duration = event.get("duration_ms")
        if (
            url
            and isinstance(duration, int)
            and event.get("status")
            in {
                "received",
                "revalidated",
            }
        ):
            host = urlparse(url).hostname or url
            domain_durations.setdefault(host, []).append(duration)
    return {
        "requests": requests,
        "retries": retries,
        "timeouts": timeouts,
        "domains": {
            host: _latency_histogram(durations)
            for host, durations in sorted(domain_durations.items())
        },
    }


def _refresh_is_degraded(previous: BundleRecord, current: BundleRecord) -> bool:
    """Whether a refresh crawl lost previously-present pages without
    definitive evidence they are gone.

    A fresh bundle must not replace a complete cached bundle when the crawl
    was short for non-definitive reasons: transient per-page failures, robots
    rejections, or request/page limits (``current.incomplete``), or pages
    that vanished from the result without an HTTP 404/410 observation.
    Genuine deletions (definitive absence) keep the refresh faithful.
    """
    if current.incomplete:
        return True
    previous_urls = {page.final_url or page.requested_url for page in previous.pages}
    current_urls = {page.final_url or page.requested_url for page in current.pages}
    absent = set(current.absent_urls)
    return bool(previous_urls - current_urls - absent)


def bundle_refresh_diff(
    previous: BundleRecord | None, current: BundleRecord
) -> dict[str, Any]:
    """Summarize what a refresh actually changed between two crawled bundles.

    Pages are keyed by their final URL; each entry records the content-hash
    delta so operators can see added, removed, and changed URLs at a glance.
    """

    def _keyed(bundle: BundleRecord) -> dict[str, str]:
        return {
            (page.final_url or page.requested_url): page.content_sha256
            for page in bundle.pages
        }

    if previous is None:
        return {"had_previous": False}
    old_pages = _keyed(previous)
    new_pages = _keyed(current)
    added = sorted(set(new_pages) - set(old_pages))
    removed = sorted(set(old_pages) - set(new_pages))
    changed = sorted(
        url
        for url in set(old_pages) & set(new_pages)
        if old_pages[url] != new_pages[url]
    )
    return {
        "had_previous": True,
        "added": [{"url": url, "content_sha256": new_pages[url]} for url in added],
        "removed": [{"url": url, "content_sha256": old_pages[url]} for url in removed],
        "changed": [
            {
                "url": url,
                "old_content_sha256": old_pages[url],
                "new_content_sha256": new_pages[url],
            }
            for url in changed
        ],
        "unchanged": len(set(old_pages) & set(new_pages)) - len(changed),
    }


def _fetch_cache_path(cache_root: Path) -> Path:
    return cache_root / "fetches" / "index.json"


def _load_fetch_cache(path: Path) -> dict[str, ConditionalEntry]:
    """Restore prior fetch metadata for conditional revalidation requests."""
    if not path.exists() or path.is_symlink():
        return {}
    try:
        payload = _read_json(path)
        if (
            payload.get("cache_version") != CACHE_VERSION
            or payload.get("pipeline_version") != PIPELINE_VERSION
        ):
            return {}
        raw = payload.get("entries")
        if not isinstance(raw, dict):
            return {}
        entries: dict[str, ConditionalEntry] = {}
        for url, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            try:
                entries[str(url)] = ConditionalEntry.from_dict(entry)
            except (KeyError, TypeError, ValueError, binascii.Error):
                continue
        return entries
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {}


def _store_fetch_cache(cache_root: Path, entries: dict[str, ConditionalEntry]) -> None:
    """Merge new fetch metadata into the shared cache under a lock.

    The file is shared by every profile and target in the output directory,
    so a plain whole-file write would silently drop entries another run
    wrote after our load. The lock covers the load-modify-write window;
    per-run entries win on conflict because they are the fresh reads.
    """
    path = _fetch_cache_path(cache_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with interprocess_lock(cache_root / "fetches" / "index.lock"):
        current = _load_fetch_cache(path)
        current.update(entries)
        payload = {
            "pipeline_version": PIPELINE_VERSION,
            "cache_version": CACHE_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "entries": {url: entry.to_dict() for url, entry in sorted(current.items())},
        }
        _write_json(path, payload)


def _generator_cache_key(generator: SkillGenerator) -> str:
    """Return a stable generator configuration key, including custom backends."""
    cache_key = getattr(generator, "cache_key", None)
    configured = cache_key() if callable(cache_key) else generator.name
    return f"{type(generator).__module__}.{type(generator).__qualname__}:{configured}"


def _draft_cache_path(
    cache_root: Path,
    profile: SourceProfile,
    target: TargetSpec,
    corpus_fingerprint: str,
    generator_fingerprint: str,
) -> Path:
    return (
        cache_root
        / "drafts"
        / (
            f"{slugify(profile.id)}--{slugify(target.id)}--"
            f"{corpus_fingerprint[:20]}--{generator_fingerprint[:20]}.json"
        )
    )


def _cached_draft(
    path: Path,
    *,
    corpus_fingerprint: str,
    generator_fingerprint: str,
    generation_config_fingerprint: str,
    profile_fingerprint: str,
    target_id: str,
    target_fingerprint: str,
) -> SkillDraft | None:
    if not path.exists() or path.is_symlink():
        return None
    try:
        payload = _read_json(path)
        if (
            payload.get("cache_version") != CACHE_VERSION
            or payload.get("pipeline_version") != PIPELINE_VERSION
            or payload.get("corpus_fingerprint") != corpus_fingerprint
            or payload.get("generator_fingerprint") != generator_fingerprint
            or payload.get("generation_config_fingerprint")
            != generation_config_fingerprint
            or payload.get("profile_fingerprint") != profile_fingerprint
            or payload.get("target_id") != target_id
            or payload.get("target_fingerprint") != target_fingerprint
        ):
            return None
        draft_payload = payload["draft"]
        if payload.get("draft_sha256") != sha256_json(draft_payload):
            return None
        draft = SkillDraft.from_payload(draft_payload)
        validate_generated_body(
            draft.body,
            provider_output=draft.generator != "deterministic",
            description=draft.description,
        )
        return draft
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _write_draft_cache(
    path: Path,
    draft: SkillDraft,
    *,
    corpus_fingerprint: str,
    generator_fingerprint: str,
    generation_config_fingerprint: str,
    profile_fingerprint: str,
    target_id: str,
    target_fingerprint: str,
) -> None:
    draft_payload = draft.to_payload()
    _write_json(
        path,
        {
            "pipeline_version": PIPELINE_VERSION,
            "cache_version": CACHE_VERSION,
            "corpus_fingerprint": corpus_fingerprint,
            "generator_fingerprint": generator_fingerprint,
            "generation_config_fingerprint": generation_config_fingerprint,
            "profile_fingerprint": profile_fingerprint,
            "target_id": target_id,
            "target_fingerprint": target_fingerprint,
            "draft_sha256": sha256_json(draft_payload),
            "draft": draft_payload,
        },
    )


def _run_id(
    profile: SourceProfile,
    target_ids: list[str],
    generator_fingerprint: str,
    generation_config_fingerprint: str,
) -> str:
    fingerprint = sha256_json(
        {
            "pipeline_version": PIPELINE_VERSION,
            "profile_fingerprint": profile.fingerprint(),
            "target_ids": target_ids,
            "generator_fingerprint": generator_fingerprint,
            "generation_config_fingerprint": generation_config_fingerprint,
        }
    )
    return f"{slugify(profile.id)}--{fingerprint[:20]}"


def _ensure_trace(
    draft: SkillDraft, generator: SkillGenerator, cache_key: str
) -> SkillDraft:
    validate_generated_body(
        draft.body,
        provider_output=draft.generator != "deterministic",
        description=draft.description,
    )
    if draft.trace is not None:
        return draft
    attempt = GenerationAttempt(
        backend=draft.generator or generator.name,
        model=str(getattr(generator, "model"))
        if getattr(generator, "model", None)
        else None,
        status="success",
        started_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=0,
        retries=0,
        cache_key=cache_key,
    )
    return replace(
        draft,
        trace=GenerationTrace(
            attempts=(attempt,),
            selected_backend=draft.generator or generator.name,
            fallback_used=False,
            fallback_chain=(draft.generator or generator.name,),
        ),
    )


def _enforce_target_name(draft: SkillDraft, target_name: str) -> SkillDraft:
    """Make provider-suggested names metadata only; paths follow the target spec."""
    if draft.name == target_name:
        return draft
    metadata = dict(draft.metadata)
    metadata.setdefault("model_suggested_name", draft.name)
    return replace(draft, name=target_name, metadata=metadata)


def _apply_target_description(draft: SkillDraft, target: TargetSpec) -> SkillDraft:
    """An authored target description is authoritative for the frontmatter."""
    if not target.description or draft.description == target.description:
        return draft
    metadata = dict(draft.metadata)
    metadata.setdefault("generator_description", draft.description)
    return replace(draft, description=target.description, metadata=metadata)


def _state_writer(run_root: Path, run_id: str):
    history: list[dict[str, Any]] = []
    state_path = run_root / "state.json"
    state_lock = run_root.parent.parent / ".cache" / "locks" / f"{run_id}.state.lock"
    try:
        existing = _read_json(state_path)
        if isinstance(existing.get("history"), list):
            history = [item for item in existing["history"] if isinstance(item, dict)]
    except (OSError, ValueError, json.JSONDecodeError):
        pass

    def transition(state: str, **details: Any) -> None:
        with interprocess_lock(state_lock):
            current_history: list[dict[str, Any]] = []
            try:
                existing = _read_json(state_path)
                if isinstance(existing.get("history"), list):
                    current_history = [
                        item for item in existing["history"] if isinstance(item, dict)
                    ]
            except (OSError, ValueError, json.JSONDecodeError):
                current_history = list(history)
            event = {
                "state": state,
                "at": datetime.now(timezone.utc).isoformat(),
                **details,
            }
            current_history.append(event)
            history[:] = current_history
            _write_json(
                state_path,
                {
                    "pipeline_version": PIPELINE_VERSION,
                    "run_id": run_id,
                    "state": state,
                    "history": current_history,
                },
            )

    return transition


def _generation_from_options(
    profile: SourceProfile,
    *,
    backend: str | None,
    model: str | None,
    fallback_backend: str | None,
    ollama_model: str | None,
    ollama_url: str | None,
    ollama_timeout_seconds: float | None,
    ollama_num_ctx: int | None,
    ollama_max_prompt_chars: int | None,
) -> GenerationConfig:
    return profile.generation.with_overrides(
        backend=backend,
        model=model,
        fallback_backend=fallback_backend,
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        ollama_timeout_seconds=ollama_timeout_seconds,
        ollama_num_ctx=ollama_num_ctx,
        ollama_max_prompt_chars=ollama_max_prompt_chars,
    )


def run_profile(
    profile: SourceProfile,
    *,
    output_dir: str | Path,
    backend: str | None = None,
    target_ids: Iterable[str] | None = None,
    refresh: bool = False,
    force_process: bool = False,
    model: str | None = None,
    command: list[str] | None = None,
    fallback_backend: str | None = None,
    ollama_model: str | None = None,
    ollama_url: str | None = None,
    ollama_timeout_seconds: float | None = None,
    ollama_num_ctx: int | None = None,
    ollama_max_prompt_chars: int | None = None,
    generator: SkillGenerator | None = None,
    evidence_origin: str | None = None,
) -> list[Path]:
    """Run selected targets with stable, cacheable stage identities and recovery state."""
    local_source = urlparse(profile.base_url).hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    origin = evidence_origin or ("fixture" if local_source else "unknown")
    if origin not in {"fixture", "live", "unknown"} or (
        local_source and origin == "live"
    ):
        raise ValueError("invalid evidence origin for this source profile")
    output = Path(output_dir)
    selected = set(target_ids) if target_ids is not None else None
    active_targets = [
        target
        for target in profile.targets
        if selected is None or target.id in selected
    ]
    if selected is not None:
        unknown = selected - {target.id for target in profile.targets}
        if unknown:
            raise KeyError(f"unknown target(s): {', '.join(sorted(unknown))}")
    if not active_targets:
        raise ValueError("no targets selected")

    generation = _generation_from_options(
        profile,
        backend=backend,
        model=model,
        fallback_backend=fallback_backend,
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        ollama_timeout_seconds=ollama_timeout_seconds,
        ollama_num_ctx=ollama_num_ctx,
        ollama_max_prompt_chars=ollama_max_prompt_chars,
    )
    active_generator = generator or generator_for(
        generation.backend,
        model=generation.model,
        command=command,
        fallback_backend=generation.fallback_backend,
        ollama_model=generation.ollama_model,
        ollama_url=generation.ollama_url,
        ollama_timeout_seconds=generation.ollama_timeout_seconds,
        ollama_num_ctx=generation.ollama_num_ctx,
        ollama_max_prompt_chars=generation.ollama_max_prompt_chars,
        retry=generation.retry,
    )
    profile_fingerprint = profile.fingerprint()
    generation_config_fingerprint = generation.fingerprint()
    generator_fingerprint = sha256_text(_generator_cache_key(active_generator))
    target_id_list = [target.id for target in active_targets]
    run_id = _run_id(
        profile, target_id_list, generator_fingerprint, generation_config_fingerprint
    )
    run_root = output / "runs" / run_id
    cache_root = output / ".cache"
    run_root.mkdir(parents=True, exist_ok=True)
    transition = _state_writer(run_root, run_id)
    transition("planned", profile_id=profile.id, targets=target_id_list)
    rendered: list[Path] = []
    render_records: list[dict[str, Any]] = []
    acquired_bundles: list[BundleRecord] = []
    refresh_diffs: dict[str, dict[str, Any]] = {}
    refresh_degraded_by_target: dict[str, bool] = {}

    try:
        fetch_cache_file = _fetch_cache_path(cache_root)
        fetch_cache = _load_fetch_cache(fetch_cache_file)
        with WebsiteCrawler(
            profile, refresh=refresh, fetch_cache=fetch_cache
        ) as crawler:
            for target in active_targets:
                lock_path = (
                    cache_root
                    / "locks"
                    / f"{slugify(profile.id)}--{slugify(target.id)}.lock"
                )
                with interprocess_lock(lock_path):
                    transition("acquiring", target_id=target.id)
                    cache_file = _bundle_cache_path(cache_root, profile, target)
                    previous_bundle = (
                        _cached_bundle(
                            cache_file,
                            profile_fingerprint=profile_fingerprint,
                            target_id=target.id,
                            target_fingerprint=target.fingerprint(),
                        )
                        if refresh
                        else None
                    )
                    bundle = (
                        None
                        if refresh
                        else _cached_bundle(
                            cache_file,
                            profile_fingerprint=profile_fingerprint,
                            target_id=target.id,
                            target_fingerprint=target.fingerprint(),
                        )
                    )
                    acquisition_cache_hit = bundle is not None
                    if bundle is None:
                        bundle = crawler.crawl(target)
                        _store_fetch_cache(cache_root, crawler.fetch_cache)
                        degraded = bool(
                            refresh
                            and previous_bundle is not None
                            and _refresh_is_degraded(previous_bundle, bundle)
                        )
                        if refresh:
                            refresh_degraded_by_target[target.id] = degraded
                        if not degraded:
                            _write_bundle_cache(
                                cache_file,
                                bundle,
                                profile_fingerprint=profile_fingerprint,
                                target_id=target.id,
                                target_fingerprint=target.fingerprint(),
                            )
                        else:
                            transition(
                                "acquiring",
                                target_id=target.id,
                                refresh_degraded=True,
                                note=(
                                    "refresh crawl was not faithful to the previous "
                                    "bundle; the previous cached bundle is retained"
                                ),
                            )
                    if refresh:
                        refresh_diffs[target.id] = bundle_refresh_diff(
                            previous_bundle, bundle
                        )
                    acquired_bundles.append(bundle)
                    target_slug = slugify(target.id)
                    _write_json(
                        run_root / "01_acquire" / f"{target_slug}.json",
                        bundle.to_dict(),
                    )

                    transition("preparing", target_id=target.id)
                    corpus = prepare_corpus(
                        bundle,
                        max_chars_per_page=profile.extraction.max_chars_per_page,
                        profile_fingerprint=profile_fingerprint,
                    )
                    _write_json(
                        run_root / "02_prepare" / f"{target_slug}.json",
                        corpus.to_payload(),
                    )

                    include_retrieval = bool(
                        getattr(active_generator, "requires_retrieval", False)
                    )
                    corpus_fingerprint = corpus.fingerprint(
                        include_retrieval=include_retrieval
                    )
                    draft_cache_file = _draft_cache_path(
                        cache_root,
                        profile,
                        target,
                        corpus_fingerprint,
                        generator_fingerprint,
                    )
                    transition("generating", target_id=target.id)
                    draft = (
                        None
                        if force_process
                        else _cached_draft(
                            draft_cache_file,
                            corpus_fingerprint=corpus_fingerprint,
                            generator_fingerprint=generator_fingerprint,
                            generation_config_fingerprint=generation_config_fingerprint,
                            profile_fingerprint=profile_fingerprint,
                            target_id=target.id,
                            target_fingerprint=target.fingerprint(),
                        )
                    )
                    process_cache_hit = draft is not None
                    if draft is None:
                        draft = active_generator.generate(corpus)
                        draft = _enforce_target_name(draft, corpus.skill_name)
                        draft = _apply_target_description(draft, target)
                        draft = _ensure_trace(
                            draft,
                            active_generator,
                            _generator_cache_key(active_generator),
                        )
                        _write_draft_cache(
                            draft_cache_file,
                            draft,
                            corpus_fingerprint=corpus_fingerprint,
                            generator_fingerprint=generator_fingerprint,
                            generation_config_fingerprint=generation_config_fingerprint,
                            profile_fingerprint=profile_fingerprint,
                            target_id=target.id,
                            target_fingerprint=target.fingerprint(),
                        )
                    else:
                        draft = _enforce_target_name(draft, corpus.skill_name)
                        draft = _apply_target_description(draft, target)
                        draft = _ensure_trace(
                            draft,
                            active_generator,
                            _generator_cache_key(active_generator),
                        )
                    process_path = run_root / "03_process" / f"{target_slug}.json"
                    process_payload = draft.to_payload()
                    process_payload.update(
                        {
                            "corpus_fingerprint": corpus_fingerprint,
                            "generator_fingerprint": generator_fingerprint,
                            "generation_config_fingerprint": generation_config_fingerprint,
                            "cache_hit": process_cache_hit,
                        }
                    )
                    _write_json(process_path, process_payload)

                    transition("validating", target_id=target.id)
                    parsed_draft = SkillDraft.from_payload(_read_json(process_path))
                    _write_json(
                        run_root / "04_parse" / f"{target_slug}.json",
                        {
                            "valid": True,
                            "draft_sha256": sha256_json(parsed_draft.to_payload()),
                            "name": parsed_draft.name,
                            "description": parsed_draft.description,
                            "generation_trace": parsed_draft.trace.to_dict()
                            if parsed_draft.trace
                            else None,
                        },
                    )
                    skill_path = render_skill(
                        parsed_draft,
                        corpus,
                        output / "skills",
                        run_id=run_id,
                        cache_identity={
                            "pipeline_version": PIPELINE_VERSION,
                            "cache_version": CACHE_VERSION,
                            "request_count": corpus.request_count,
                            "corpus_fingerprint": corpus_fingerprint,
                            "profile_fingerprint": profile_fingerprint,
                            "target_fingerprint": target.fingerprint(),
                            "generation_config_fingerprint": generation_config_fingerprint,
                        },
                        generator_fingerprint=generator_fingerprint,
                    )
                    snapshot_dir = run_root / "05_render"
                    if corpus.area:
                        snapshot_dir = snapshot_dir / artifact_name(corpus.area)
                    snapshot_dir = snapshot_dir / target_slug
                    snapshot_dir.mkdir(parents=True, exist_ok=True)
                    snapshot_skill = snapshot_dir / "SKILL.md"
                    write_bytes_atomic(snapshot_skill, skill_path.read_bytes())
                    references_source = skill_path.parent / "references"
                    if references_source.is_symlink() or not references_source.is_dir():
                        raise ValueError(
                            f"rendered package references directory must be a "
                            f"regular directory, not a symlink: {references_source}"
                        )
                    # The run snapshot must carry the complete package payload
                    # byte-exactly, so downstream validation of the snapshot
                    # sees the same provenance artifacts as the canonical
                    # package. The renderer always emits every file below for
                    # the current manifest schema, so any absence or symlink
                    # here is a hard failure, never a silent skip.
                    for packaged in (
                        "manifest.json",
                        "regeneration.json",
                        "references/sources.json",
                    ):
                        packaged_source = skill_path.parent / packaged
                        if (
                            packaged_source.is_symlink()
                            or not packaged_source.is_file()
                        ):
                            raise ValueError(
                                f"rendered package is missing a required "
                                f"provenance artifact, or it is not a regular "
                                f"file: {packaged_source}"
                            )
                        packaged_snapshot = snapshot_dir / packaged
                        packaged_snapshot.parent.mkdir(parents=True, exist_ok=True)
                        write_bytes_atomic(
                            packaged_snapshot, packaged_source.read_bytes()
                        )
                    rendered.append(skill_path)
                    render_records.append(
                        {
                            "target_id": target.id,
                            "evidence_origin": "unknown"
                            if origin == "live" and acquisition_cache_hit
                            else origin,
                            "skill_path": str(skill_path),
                            "skill_sha256": sha256_text(
                                skill_path.read_text(encoding="utf-8")
                            ),
                            "request_count": corpus.request_count,
                            "acquisition_cache_hit": acquisition_cache_hit,
                            "process_cache_hit": process_cache_hit,
                            "package_snapshot": str(snapshot_skill.relative_to(output)),
                            "generation_trace": parsed_draft.trace.to_dict()
                            if parsed_draft.trace
                            else None,
                        }
                    )

        transition("rendered", targets=target_id_list)
        with interprocess_lock(cache_root / "locks" / "index.lock"):
            index_path = write_skill_index(output / "skills")
        for record in render_records:
            target_slug = slugify(record["target_id"])
            _write_json(
                run_root / "05_render" / f"{target_slug}.json",
                {**record, "skill_index": str(index_path)},
            )
        _write_json(
            run_root / "manifest.json",
            {
                "pipeline_version": PIPELINE_VERSION,
                "cache_version": CACHE_VERSION,
                "run_id": run_id,
                "state": "rendered",
                "profile_id": profile.id,
                "profile_base_url": profile.base_url,
                "area": profile.area,
                "profile_fingerprint": profile_fingerprint,
                "generation_config": generation.to_dict(),
                "generation_config_fingerprint": generation_config_fingerprint,
                "generator": active_generator.name,
                "generator_fingerprint": generator_fingerprint,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "request_count": sum(
                    int(record.get("request_count", 0)) for record in render_records
                ),
                "acquisition_metrics": acquisition_metrics(
                    (event for bundle in acquired_bundles for event in bundle.events)
                ),
                "force_process": force_process,
                "refresh": refresh,
                "refresh_diff": refresh_diffs,
                "refresh_degraded": refresh_degraded_by_target,
                "evidence_origin": origin,
                "skill_index": str(index_path),
                "targets": [str(path) for path in rendered],
                "target_records": render_records,
            },
        )
        return rendered
    except Exception as exc:
        safe_error = _sanitize_error(exc)
        transition("failed", error_type=type(exc).__name__, error=safe_error)
        failure_trace = getattr(exc, "generation_trace", None)
        failure = {
            "pipeline_version": PIPELINE_VERSION,
            "cache_version": CACHE_VERSION,
            "run_id": run_id,
            "state": "failed",
            "profile_id": profile.id,
            "profile_base_url": profile.base_url,
            "area": profile.area,
            "error_type": type(exc).__name__,
            "error": safe_error,
            "generator": active_generator.name,
            "generator_fingerprint": generator_fingerprint,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generation_config_fingerprint": generation_config_fingerprint,
            "generation_trace": (
                failure_trace.to_dict()
                if isinstance(failure_trace, GenerationTrace)
                else None
            ),
            "evidence_origin": origin,
            "request_count": sum(
                int(record.get("request_count", 0)) for record in render_records
            ),
            "acquisition_metrics": acquisition_metrics(
                (event for bundle in acquired_bundles for event in bundle.events)
            ),
            "force_process": force_process,
            "refresh": refresh,
            "refresh_diff": refresh_diffs,
            "refresh_degraded": refresh_degraded_by_target,
            "targets": [str(path) for path in rendered],
            "target_records": render_records,
        }
        _write_json(run_root / "failure.json", failure)
        _write_json(run_root / "manifest.json", failure)
        raise


def run_profile_from_path(
    profile_path: str | Path,
    *,
    output_dir: str | Path,
    backend: str | None = None,
    target_ids: Iterable[str] | None = None,
    refresh: bool = False,
    force_process: bool = False,
    model: str | None = None,
    command: list[str] | None = None,
    fallback_backend: str | None = None,
    ollama_model: str | None = None,
    ollama_url: str | None = None,
    ollama_timeout_seconds: float | None = None,
    ollama_num_ctx: int | None = None,
    ollama_max_prompt_chars: int | None = None,
    evidence_origin: str | None = None,
) -> list[Path]:
    """Load a YAML profile and execute it."""
    return run_profile(
        load_profile(profile_path),
        output_dir=output_dir,
        evidence_origin=evidence_origin,
        backend=backend,
        target_ids=target_ids,
        refresh=refresh,
        force_process=force_process,
        model=model,
        command=command,
        fallback_backend=fallback_backend,
        ollama_model=ollama_model,
        ollama_url=ollama_url,
        ollama_timeout_seconds=ollama_timeout_seconds,
        ollama_num_ctx=ollama_num_ctx,
        ollama_max_prompt_chars=ollama_max_prompt_chars,
    )


def inspect_cache(
    output_dir: str | Path, profile: SourceProfile | None = None
) -> dict[str, Any]:
    """Report valid, stale, corrupt, and unknown cache envelopes without mutation."""
    root = Path(output_dir) / ".cache"
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")) if root.exists() else []:
        if profile is not None and not path.name.startswith(f"{profile.id}--"):
            continue
        record: dict[str, Any] = {"path": str(path), "status": "stale"}
        try:
            if path.is_symlink():
                record["status"] = "corrupt"
                record["reason"] = "symlink cache entry"
                records.append(record)
                continue
            payload = _read_json(path)
            if (
                payload.get("pipeline_version") != PIPELINE_VERSION
                or payload.get("cache_version") != CACHE_VERSION
            ):
                record["reason"] = "schema version mismatch"
            elif (
                profile is not None
                and "bundle" in payload
                and (
                    payload.get("profile_fingerprint") != profile.fingerprint()
                    or payload.get("target_id")
                    not in {target.id for target in profile.targets}
                    or payload.get("target_fingerprint")
                    != profile.target(str(payload.get("target_id"))).fingerprint()
                )
            ):
                record["reason"] = "profile or target fingerprint is stale"
            elif (
                profile is not None
                and "draft" in payload
                and (
                    payload.get("profile_fingerprint") != profile.fingerprint()
                    or payload.get("target_id")
                    not in {target.id for target in profile.targets}
                    or payload.get("target_fingerprint")
                    != profile.target(str(payload.get("target_id"))).fingerprint()
                )
            ):
                record["reason"] = "profile or target fingerprint is stale"
            elif "bundle" in payload and payload.get("bundle_sha256") != sha256_json(
                payload["bundle"]
            ):
                record["status"] = "corrupt"
                record["reason"] = "bundle hash mismatch"
            elif "draft" in payload and payload.get("draft_sha256") != sha256_json(
                payload["draft"]
            ):
                record["status"] = "corrupt"
                record["reason"] = "draft hash mismatch"
            else:
                record["status"] = "valid"
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            record["status"] = "corrupt"
            record["reason"] = type(exc).__name__
        records.append(record)
    counts = {
        status: sum(item["status"] == status for item in records)
        for status in ("valid", "stale", "corrupt")
    }
    return {
        "pipeline_version": PIPELINE_VERSION,
        "cache_version": CACHE_VERSION,
        "counts": counts,
        "entries": records,
    }
