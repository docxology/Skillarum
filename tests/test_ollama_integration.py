"""Opt-in integration check against a real Ollama daemon and local model."""

from __future__ import annotations

import os

import pytest

from skillarum.generators import generator_for
from skillarum.models import PreparedCorpus, PreparedPage


@pytest.mark.skipif(
    os.getenv("SKILLARUM_RUN_OLLAMA") != "1",
    reason="set SKILLARUM_RUN_OLLAMA=1 with a running Ollama model for live coverage",
)
def test_ollama_generator_live() -> None:
    corpus = PreparedCorpus(
        profile_id="integration",
        profile_name="Integration",
        target_id="test",
        skill_name="Integration-Test",
        pages=(
            PreparedPage(
                url="https://example.org",
                title="Example",
                headings=("Example",),
                text="This is a small source-grounded integration test.",
                links=(),
            ),
        ),
    )
    generator = generator_for(
        "ollama",
        ollama_model=os.getenv("SKILLARUM_OLLAMA_MODEL", "llama3.2"),
        ollama_url=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        fallback_backend="deterministic",
    )
    draft = generator.generate(corpus)
    assert draft.name
    assert draft.description
    assert draft.body
    assert draft.trace is not None
    assert any(attempt.backend == "ollama" for attempt in draft.trace.attempts)
