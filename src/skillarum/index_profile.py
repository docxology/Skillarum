"""Derive explicit one-page targets from a site's own index page.

An index page (a wiki ``Index``, a table of contents, a sitemap rendered as
HTML) already states which pages a site's author considers part of a
collection and how they group them. This module turns that statement into
ordinary profile targets: one exact URL per target, no spidering, with the
index's own grouping retained as a section label.

Parsing is pure and offline (:func:`parse_index`). Acquisition of the index
page itself goes through :class:`~skillarum.crawler.WebsiteCrawler`, so the
same robots, origin, SSRF, and request-budget rules apply as for any page.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml
from bs4 import BeautifulSoup

from .models import SourceProfile
from .urls import normalize_url, resolve_url, same_origin
from .utils import sha256_bytes, slugify

_SECTION_TAGS = {"strong", "b", "h1", "h2", "h3", "h4", "h5", "h6", "dt"}
_DESCRIPTION_LIMIT = 1024


@dataclass(frozen=True)
class IndexEntry:
    """One page listed by an index, in the index's own order."""

    url: str
    label: str
    section: str

    @property
    def page_name(self) -> str:
        """The final path segment, percent-decoded and folded to ASCII."""
        segment = unquote(urlparse(self.url).path.rstrip("/").rsplit("/", 1)[-1])
        folded = unicodedata.normalize("NFKD", segment)
        return "".join(ch for ch in folded if ord(ch) < 128) or "page"


def _section_label(node: Any) -> str | None:
    for parent in [node, *node.parents]:
        if getattr(parent, "name", None) in _SECTION_TAGS:
            return " ".join(parent.get_text(" ", strip=True).split()) or None
    return None


def parse_index(
    html: bytes | str,
    *,
    page_url: str,
    prefix: str,
    main_selector: str | None = None,
    include_self: bool = True,
) -> list[IndexEntry]:
    """Return de-duplicated same-origin links under ``prefix`` in document order.

    The section of an entry is the text of the most recent bold or heading
    element seen before it (an entry that is itself bold names its own
    section). Links with a query string or fragment-only targets are skipped:
    on wikis they are edit, history, or search actions rather than pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(main_selector) if main_selector else None
    root = root or soup.body or soup
    base = normalize_url(page_url)
    origin_prefix = urlparse(base)._replace(path=prefix, query="", fragment="")
    wanted = origin_prefix.geturl()
    section = ""
    entries: dict[str, IndexEntry] = {}
    for node in root.find_all(True):
        if node.name in _SECTION_TAGS:
            label = " ".join(node.get_text(" ", strip=True).split())
            if label:
                section = label
        if node.name != "a" or not node.get("href"):
            continue
        href = str(node.get("href")).strip()
        if href.startswith("#"):
            continue
        try:
            url = normalize_url(resolve_url(base, href))
        except (TypeError, ValueError):
            continue
        parsed = urlparse(url)
        if parsed.query or not same_origin(base, url) or not url.startswith(wanted):
            continue
        url = parsed._replace(fragment="").geturl()
        if url == base and not include_self:
            continue
        if url in entries:
            continue
        label = " ".join(node.get_text(" ", strip=True).split()) or url
        entries[url] = IndexEntry(
            url=url, label=label, section=_section_label(node) or section
        )
    return list(entries.values())


def _description(entry: IndexEntry, *, profile_name: str, index_url: str) -> str:
    path = urlparse(entry.url).path
    label = entry.label
    parts = [
        f"Source-grounded reference for the {profile_name} page {path}",
        f'titled "{label}"' if label else "",
    ]
    text = " ".join(part for part in parts if part) + "."
    if entry.section and entry.section != entry.label:
        text += f' Listed under "{entry.section}" in the index at {index_url}.'
    else:
        text += f" Listed in the index at {index_url}."
    text += (
        " Use when a task needs what this page states, cited to its URL, kept"
        " separate from the agent's own interpretation."
    )
    text = text.replace("<", "(").replace(">", ")")
    return text[:_DESCRIPTION_LIMIT]


def targets_from_entries(
    entries: list[IndexEntry],
    *,
    profile_name: str,
    index_url: str,
    id_prefix: str,
    name_prefix: str,
) -> list[dict[str, Any]]:
    """Render entries as profile target mappings with stable unique ids."""
    targets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for entry in entries:
        name = f"{name_prefix}{entry.page_name}"
        target_id = slugify(f"{id_prefix}-{entry.page_name}")
        base_id, base_name, counter = target_id, name, 2
        while target_id in seen_ids or slugify(name) in seen_names:
            target_id, name = f"{base_id}-{counter}", f"{base_name}-{counter}"
            counter += 1
        seen_ids.add(target_id)
        seen_names.add(slugify(name))
        target: dict[str, Any] = {
            "id": target_id,
            "name": name,
            "urls": [urlparse(entry.url).path],
            "description": _description(
                entry, profile_name=profile_name, index_url=index_url
            ),
        }
        if entry.section:
            target["section"] = entry.section
        targets.append(target)
    return targets


def build_index_profile(
    base: SourceProfile,
    entries: list[IndexEntry],
    *,
    index_url: str,
    index_sha256: str,
    retrieved_at: str,
    profile_id: str,
    id_prefix: str,
    name_prefix: str,
    preserve_blocks: bool = True,
    title_separator: str | None = None,
) -> dict[str, Any]:
    """Return a complete profile mapping whose targets come from an index.

    Crawl and generation settings are copied from ``base``; page and request
    budgets are raised to cover every target exactly once. The index receipt
    (URL, retrieval time, content hash, entry count) is recorded under
    ``derived_from`` so the target list is itself traceable.
    """
    data = base.to_dict()
    crawl = dict(data["crawl"])
    crawl.update(
        {
            "follow_links": False,
            "max_depth": 0,
            "max_pages": max(int(crawl["max_pages"]), len(entries)),
            "max_requests": max(int(crawl["max_requests"]), 3 * len(entries) + 10),
        }
    )
    crawl.pop("user_agent", None)
    extraction = dict(data["extraction"])
    extraction["preserve_blocks"] = preserve_blocks
    if title_separator:
        extraction["title_separator"] = title_separator
    generation = {
        key: data["generation"][key]
        for key in ("backend", "model", "ollama_model", "retry")
        if key in data["generation"]
    }
    targets = targets_from_entries(
        entries,
        profile_name=base.name,
        index_url=index_url,
        id_prefix=id_prefix,
        name_prefix=name_prefix,
    )
    return {
        "id": profile_id,
        "name": base.name,
        "base_url": base.base_url,
        "area": base.area,
        "derived_from": {
            "index_url": index_url,
            "retrieved_at": retrieved_at,
            "content_sha256": index_sha256,
            "entry_count": len(entries),
            "sections": sorted({entry.section for entry in entries if entry.section}),
        },
        "crawl": crawl,
        "extraction": extraction,
        "generation": generation,
        "targets": targets,
    }


def fetch_index(base: SourceProfile, index_url: str) -> tuple[bytes, str, str]:
    """Fetch one index page through the crawler's safety rules.

    Returns ``(content, final_url, retrieved_at)``.
    """
    from .crawler import WebsiteCrawler

    if not same_origin(base.base_url, index_url):
        raise ValueError(f"index URL is outside the profile origin: {index_url}")
    with WebsiteCrawler(base, refresh=True) as crawler:
        content, final_url = crawler.fetch_raw(index_url)
    return content, final_url, datetime.now(timezone.utc).isoformat()


def write_index_profile(
    base: SourceProfile,
    *,
    index_url: str,
    prefix: str,
    output: Path,
    profile_id: str,
    id_prefix: str,
    name_prefix: str,
    html_path: Path | None = None,
    title_separator: str | None = None,
    preserve_blocks: bool = True,
) -> dict[str, Any]:
    """Fetch (or read) an index page, derive targets, and write a YAML profile."""
    if html_path is not None:
        content = html_path.read_bytes()
        final_url = normalize_url(index_url)
        retrieved_at = datetime.fromtimestamp(
            html_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    else:
        content, final_url, retrieved_at = fetch_index(base, index_url)
    entries = parse_index(
        content,
        page_url=final_url,
        prefix=prefix,
        main_selector=base.extraction.main_selector,
    )
    if not entries:
        raise ValueError(f"no links under {prefix!r} found on {final_url}")
    profile = build_index_profile(
        base,
        entries,
        index_url=final_url,
        index_sha256=sha256_bytes(content),
        retrieved_at=retrieved_at,
        profile_id=profile_id,
        id_prefix=id_prefix,
        name_prefix=name_prefix,
        preserve_blocks=preserve_blocks,
        title_separator=title_separator,
    )
    header = (
        f"# Generated by `skillarum profile-from-index` from {final_url}.\n"
        "# Regenerate rather than hand-editing the target list; edit crawl,\n"
        "# extraction, and generation settings in the base profile instead.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        header + yaml.safe_dump(profile, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "output": str(output),
        "index_url": final_url,
        "entry_count": len(entries),
        "sections": profile["derived_from"]["sections"],
    }
