"""YAML profile loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    CrawlConfig,
    ExtractionConfig,
    GenerationConfig,
    SourceProfile,
    TargetSpec,
)


def profile_from_mapping(value: dict[str, Any]) -> SourceProfile:
    """Build a validated profile from a YAML-shaped mapping."""
    profile_id = str(value.get("id", "")).strip()
    if not profile_id:
        raise ValueError("profile.id is required")
    name = str(value.get("name", profile_id)).strip()
    base_url = str(value.get("base_url", "")).strip()
    targets_value = value.get("targets", [])
    if not isinstance(targets_value, list):
        raise ValueError("profile.targets must be a list")
    for item in targets_value:
        if not isinstance(item, dict):
            raise ValueError("each profile target must be a mapping")
    targets = tuple(TargetSpec.from_mapping(item) for item in targets_value)
    if not targets:
        raise ValueError("profile.targets must contain at least one target")
    return SourceProfile(
        id=profile_id,
        name=name,
        base_url=base_url,
        area=str(value.get("area", "")).strip(),
        crawl=CrawlConfig.from_mapping(value.get("crawl")),
        extraction=ExtractionConfig.from_mapping(value.get("extraction")),
        generation=GenerationConfig.from_mapping(value.get("generation")),
        targets=targets,
    )


def load_profile(path: str | Path) -> SourceProfile:
    """Load and validate a YAML source profile."""
    profile_path = Path(path)
    with profile_path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if not isinstance(value, dict):
        raise ValueError(f"profile file must contain a mapping: {profile_path}")
    return profile_from_mapping(value)
