"""Tests for the secret-redaction and non-leakage gate."""

from __future__ import annotations

import pytest

from skillarum.redaction import (
    REDACTION_PLACEHOLDER,
    assert_no_secrets,
    redact_secrets,
    scan_for_secrets,
)


def test_provider_api_key_prefixes_are_redacted():
    text = "Use ghp_Abcdefghij0123456789 or sk-proj-abcdefghijklmnop for access."
    redacted, kinds = redact_secrets(text)
    assert "api_key_prefix" in kinds
    assert "ghp_" not in redacted or REDACTION_PLACEHOLDER in redacted
    assert REDACTION_PLACEHOLDER in redacted
    assert "sk-proj-abcdefghijklmnop" not in redacted


def test_jwt_is_redacted():
    text = "Authorization: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"
    redacted, kinds = redact_secrets(text)
    assert "jwt" in kinds
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted


def test_sensitive_url_params_are_redacted_but_url_structure_kept():
    text = "See https://example.com/callback?code=ok&access_token=supersecretvalue123&next=/x"
    redacted, kinds = redact_secrets(text)
    assert "sensitive_url_param" in kinds
    assert "supersecretvalue123" not in redacted
    assert "access_token=" in redacted  # parameter name survives for traceability
    assert "next=/x" in redacted


def test_luhn_valid_card_redacted_and_invalid_kept():
    card = "4111111111111111"  # Luhn-valid test Visa
    non_card = "1234567890123"  # fails Luhn
    redacted, kinds = redact_secrets(f"pay with {card} not {non_card}")
    assert "luhn_number" in kinds
    assert card not in redacted
    assert non_card in redacted


def test_redaction_is_idempotent():
    text = "token = 'xoxb-123456789-abcdefghij'"
    once, _ = redact_secrets(text)
    twice, kinds = redact_secrets(once)
    assert once == twice
    assert kinds == []  # already-redacted text is clean


def test_clean_text_passes_unchanged():
    text = "# Normal instructions\n\nRun the indexer and read sources.json."
    redacted, kinds = redact_secrets(text)
    assert redacted == text
    assert kinds == []


def test_scan_reports_kinds_without_mutating():
    text = "bearer: Abcdef123456789012345"
    kinds = scan_for_secrets(text)
    assert kinds == ["bearer"]


def test_bearer_values_are_replaced_not_preserved():
    """Negative control: the pre-fix pattern captured the credential as
    group 1, so redaction kept the secret verbatim before the placeholder."""
    text = "password: hunter2hunter2hunter2x"
    redacted, kinds = redact_secrets(text)
    assert kinds == ["bearer"]
    assert "hunter2" not in redacted
    assert redacted == "password: {secret}"
    # The two-pass guarantee holds after scrubbing: pass 2 must not fail.
    assert_no_secrets({"SKILL.md": redacted})


def test_every_redaction_kind_passes_non_leakage_gate_after_scrubbing():
    samples = {
        "api.md": "key ghp_Abcdefghij0123456789",
        "jwt.md": (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"
        ),
        "bearer.md": "password: hunter2hunter2hunter2x",
        "url.md": "https://example.com/?access_token=supersecretvalue123",
        "card.md": "4111111111111111",
    }
    for name, text in samples.items():
        redacted, kinds = redact_secrets(text)
        assert kinds, name
        assert_no_secrets({name: redacted})


def test_non_leakage_gate_raises_and_clean_passes():
    assert_no_secrets({"a.md": "no secrets here"})
    with pytest.raises(ValueError, match="non-leakage gate failed"):
        assert_no_secrets({"SKILL.md": "key: AKIAIOSFODNN7EXAMPLE"})


def test_false_positive_bias_converts_token_to_placeholder():
    # Over-redaction bias: a false positive is acceptable and reversible
    # via parameterization; the placeholder marks it explicitly.
    text = 'secret = "ThisIsAVeryLongInnocentValue12345"'
    redacted, kinds = redact_secrets(text)
    assert REDACTION_PLACEHOLDER in redacted
    assert kinds  # flagged, not silently kept
