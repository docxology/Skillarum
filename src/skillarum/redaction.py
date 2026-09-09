"""Secret redaction for rendered skill artifacts.

Two-pass defense (adopted from skillwright):
1. Pattern scrub: replace credential-shaped tokens in text before it is written.
2. Non-leakage gate: assert no secret-shaped token survives in any output payload.

Bias is over-redaction on purpose: a false positive turns a token into a
required-parameter placeholder; a false negative leaks a credential.
"""

from __future__ import annotations

import re

REDACTION_PLACEHOLDER = "{secret}"

# Ordered: more specific patterns first so narrower token shapes win.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Credential prefixes (provider API keys)
    (
        "api_key_prefix",
        re.compile(
            r"\b(?:ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|"
            r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
            r"AIza[0-9A-Za-z_-]{35})\b"
        ),
    ),
    # JWTs
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b"),
    ),
    # Bearer / authorization values in prose or URLs. Group 1 is the kept
    # key/separator prefix; the credential itself is group 2 and is replaced,
    # never preserved in the redacted output.
    (
        "bearer",
        re.compile(
            r"(?i)\b((?:bearer|token|password|passwd|secret)\s*[:=]\s*[\'\"]?)"
            r"([A-Za-z0-9_./+=-]{16,})"
        ),
    ),
    # Sensitive query/fragment keys in URLs
    (
        "sensitive_url_param",
        re.compile(
            r"(?i)([?&#](?:access_token|api_key|apikey|auth|client_secret|"
            r"key|password|private_key|secret|session_token|sid|token|sig|signature)=)"
            r"([A-Za-z0-9_./+=%-]{8,})"
        ),
    ),
)

# Luhn-valid numbers: candidate 13-19 digit runs
_LUHN_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn_valid(candidate: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", candidate)]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = (len(digits) - 2) % 2
    for index, digit in enumerate(digits[:-1]):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return (checksum + digits[-1]) % 10 == 0


def scan_for_secrets(text: str) -> list[str]:
    """Return the list of secret kinds found in *text* (empty when clean)."""
    kinds: list[str] = []
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            kinds.append(name)
    for match in _LUHN_CANDIDATE.finditer(text):
        if _luhn_valid(match.group(0)):
            kinds.append("luhn_number")
            break
    return kinds


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Scrub credential-shaped tokens from *text*.

    Returns ``(redacted_text, kinds_found)``. Repeated application is
    idempotent: already-redacted placeholders are not re-matched.
    """
    kinds: list[str] = []
    result = text
    for name, pattern in _SECRET_PATTERNS:

        def _sub(match: re.Match[str]) -> str:
            return (
                match.group(1) + REDACTION_PLACEHOLDER
                if match.lastindex
                else REDACTION_PLACEHOLDER
            )

        new_result, count = pattern.subn(_sub, result)
        if count:
            kinds.append(name)
            result = new_result

    def _luhn_sub(match: re.Match[str]) -> str:
        return REDACTION_PLACEHOLDER if _luhn_valid(match.group(0)) else match.group(0)

    new_result, count = _LUHN_CANDIDATE.subn(_luhn_sub, result)
    # count includes non-Luhn candidates; only report when something was replaced
    if REDACTION_PLACEHOLDER in new_result and "luhn_number" not in kinds:
        if new_result != result:
            kinds.append("luhn_number")
    result = new_result
    return result, kinds


def assert_no_secrets(payloads: dict[str, str]) -> None:
    """Raise ValueError when any payload still contains a secret-shaped token."""
    leaks: list[str] = []
    for name, text in payloads.items():
        for kind in scan_for_secrets(text):
            leaks.append(f"{name}: {kind}")
    if leaks:
        raise ValueError(
            "secret non-leakage gate failed (over-redaction bias applies): "
            + "; ".join(leaks)
        )
