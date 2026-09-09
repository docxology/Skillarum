"""Declarative policy packs over rendered skill content.

Adopted from attebury/skillpress skill-lint: severity-ranked regex packs over
the rendered output. The ``security`` pack is a safety check on untrusted
LLM/source-derived instruction text; ``error`` severity fails, ``warning``
reports but passes.
"""

from __future__ import annotations

import re
from typing import Any

from .redaction import REDACTION_PLACEHOLDER, redact_secrets

POLICY_PACKS: dict[str, tuple[dict[str, Any], ...]] = {
    "security": (
        {
            "id": "curl_pipe_shell",
            "pattern": re.compile(r"\bcurl\b[^\n|]*\|\s*(?:sh|bash|zsh|fish)\b"),
            "message": "instructions pipe curl into a shell interpreter",
            "severity": "error",
        },
        {
            "id": "wget_pipe_shell",
            "pattern": re.compile(r"\bwget\b[^\n|]*\|\s*(?:sh|bash|zsh|fish)\b"),
            "message": "instructions pipe wget into a shell interpreter",
            "severity": "error",
        },
        {
            "id": "sudo_usage",
            "pattern": re.compile(
                r"(?i)(?<![\w-])(?:sudo|doas)\s+(?:apt|yum|brew|pip|npm|make|systemctl|service|rm|chmod|chown|dd|mkfs|mount)\b"
            ),
            "message": "instructions invoke privilege escalation",
            "severity": "error",
        },
        {
            "id": "rm_rf",
            "pattern": re.compile(
                r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b"
            ),
            "message": "instructions recursively force-delete files",
            "severity": "error",
        },
        {
            "id": "hardcoded_secret",
            "pattern": re.compile(
                r"\b(?:ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
                r"sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
                r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.)"
            ),
            "message": "credential-shaped token appears in instructions",
            "severity": "error",
        },
        {
            "id": "absolute_home_path",
            "pattern": re.compile(
                r"(?<!\w)(?:/Users/[A-Za-z0-9_.-]+|/home/[A-Za-z0-9_.-]+|/root)/"
            ),
            "message": "instructions reference an absolute home path",
            "severity": "warning",
        },
        {
            "id": "env_var_credentials",
            "pattern": re.compile(
                r"(?i)\b(?:export|set)\s+[A-Z_]*(?:SECRET|PASSWORD|TOKEN|KEY)[A-Z_]*\s*="
            ),
            "message": "instructions set a credential-like environment variable",
            "severity": "warning",
        },
    ),
}


def run_policy(policy: str, text: str) -> dict[str, Any]:
    """Run one named policy pack over *text*.

    Returns a report dict. A finding with severity ``error`` fails the
    report; ``warning`` is informational.
    """
    if policy not in POLICY_PACKS:
        raise ValueError(f"unknown policy pack: {policy!r}")
    findings: list[dict[str, Any]] = []
    for rule in POLICY_PACKS[policy]:
        for match in rule["pattern"].finditer(text):
            excerpt, _kinds = redact_secrets(match.group(0)[:120])
            if rule["id"] == "hardcoded_secret":
                # The match itself is the credential shape; echoing any part
                # of it (even redacted) would re-leak what this rule exists to
                # catch. Offsets keep the finding locatable without content.
                excerpt = f"<{REDACTION_PLACEHOLDER}>"
            findings.append(
                {
                    "rule": rule["id"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "excerpt": excerpt,
                    "match_start": match.start(),
                    "match_end": match.end(),
                }
            )
    errors = [f for f in findings if f["severity"] == "error"]
    return {
        "ok": not errors,
        "policy": policy,
        "findings": findings,
        "error_count": len(errors),
        "warning_count": len(findings) - len(errors),
    }


def run_policies(policies: list[str], text: str) -> dict[str, Any]:
    """Run multiple policy packs; ok only when every pack passes."""
    reports = [run_policy(policy, text) for policy in policies]
    return {
        "ok": all(report["ok"] for report in reports),
        "policies": [report["policy"] for report in reports],
        "findings": [finding for report in reports for finding in report["findings"]],
        "error_count": sum(report["error_count"] for report in reports),
        "warning_count": sum(report["warning_count"] for report in reports),
    }
