"""Opt-in real OpenAI integration check; skipped in the default offline suite."""

from __future__ import annotations

import os

import pytest

from skillarum.generators import OpenAIGenerator
from skillarum.models import PreparedCorpus, PreparedPage


@pytest.mark.skipif(
    os.getenv("SKILLARUM_RUN_OPENAI") != "1",
    reason="set SKILLARUM_RUN_OPENAI=1 and install the llm extra",
)
def test_openai_generator_live() -> None:
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
    draft = OpenAIGenerator(
        model=os.getenv("SKILLARUM_OPENAI_MODEL", "gpt-4o-mini")
    ).generate(corpus)
    assert draft.name
    assert draft.description
    assert draft.body
