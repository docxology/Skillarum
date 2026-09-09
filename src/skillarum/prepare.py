"""Deterministic corpus preparation before generator execution."""

from __future__ import annotations

from .models import BundleRecord, PreparedCorpus, PreparedPage


def prepare_corpus(
    bundle: BundleRecord,
    *,
    max_chars_per_page: int,
    profile_fingerprint: str = "",
) -> PreparedCorpus:
    """Bound page context and retain truncation warnings explicitly."""
    prepared: list[PreparedPage] = []
    warnings = list(bundle.warnings)
    for page in bundle.pages:
        truncated = len(page.text) > max_chars_per_page
        text = page.text[:max_chars_per_page]
        if truncated:
            warnings.append(
                f"{page.final_url}: text truncated to {max_chars_per_page} characters"
            )
        prepared.append(
            PreparedPage(
                url=page.canonical_url or page.final_url,
                title=page.title,
                headings=page.headings,
                text=text,
                links=page.links,
                truncated=truncated,
                requested_url=page.requested_url,
                final_url=page.final_url,
                canonical_url=page.canonical_url,
                fetched_at=page.fetched_at,
                status_code=page.status_code,
                content_sha256=page.content_sha256,
                warnings=page.warnings,
            )
        )
    return PreparedCorpus(
        profile_id=bundle.profile_id,
        profile_name=bundle.profile_name,
        target_id=bundle.target_id,
        skill_name=bundle.skill_name,
        pages=tuple(prepared),
        warnings=tuple(dict.fromkeys(warnings)),
        profile_fingerprint=profile_fingerprint,
        events=tuple(dict(event) for event in bundle.events),
        request_count=bundle.request_count,
        area=bundle.area,
    )
