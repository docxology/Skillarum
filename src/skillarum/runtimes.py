"""Cross-runtime frontmatter compilation targets.

Adopted from tripleyak/SkillForge: per-target field allowlists and length
limits so one rendered skill compiles to claude, codex, and agentskills
runtime dialects without invalid fields. All three targets currently agree
on the same allowlist and limits; the mapping stays per-target so future
divergence never requires a caller change.
"""

from __future__ import annotations

from typing import Any

_SHARED_SPEC: dict[str, Any] = {
    "name_max": 64,
    "description_max": 1024,
    "allowed_fields": (
        "name",
        "description",
        "license",
        "allowed-tools",
        "metadata",
    ),
}

RUNTIME_TARGETS: dict[str, dict[str, Any]] = {
    target: dict(_SHARED_SPEC) for target in ("agentskills", "claude", "codex")
}


def compile_frontmatter(
    frontmatter: dict[str, Any], target: str
) -> tuple[dict[str, Any], list[str]]:
    """Project frontmatter onto a runtime target.

    Returns ``(compiled_frontmatter, migration_notes)``. Fields outside the
    target allowlist are dropped and recorded; length limits are enforced by
    truncation with a note (never silent).
    """
    if target not in RUNTIME_TARGETS:
        raise ValueError(f"unknown runtime target: {target!r}")
    spec = RUNTIME_TARGETS[target]
    compiled: dict[str, Any] = {}
    notes: list[str] = []
    for key, value in frontmatter.items():
        if key not in spec["allowed_fields"]:
            notes.append(f"dropped field {key!r} (not supported by {target})")
            continue
        limit = spec.get(f"{key}_max")
        if isinstance(value, str) and limit and len(value) > limit:
            notes.append(
                f"truncated field {key!r} from {len(value)} to {limit} chars for {target}"
            )
            value = value[:limit]
        compiled[key] = value
    return compiled, notes
