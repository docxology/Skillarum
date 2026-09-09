from __future__ import annotations

import pytest

from skillarum.models import (
    BundleRecord,
    CrawlConfig,
    ExtractionConfig,
    PageRecord,
    PreparedCorpus,
    SkillDraft,
    SourceProfile,
    TargetSpec,
)


def test_model_validation_and_round_trips() -> None:
    page = PageRecord(
        requested_url="https://example.org/page",
        final_url="https://example.org/page",
        canonical_url=None,
        status_code=200,
        title="Page",
        headings=("Heading",),
        text="Text",
        links=(),
        fetched_at="now",
        content_sha256="hash",
    )
    bundle = BundleRecord(
        profile_id="p",
        profile_name="Profile",
        target_id="t",
        skill_name="Skill",
        pages=(page,),
        created_at="now",
    )
    restored = BundleRecord.from_dict(bundle.to_dict())
    assert restored.pages[0].content_sha256 == "hash"
    target = TargetSpec(id="t", name="Skill", urls=("/page",))
    profile = SourceProfile(
        id="p",
        name="Profile",
        base_url="https://example.org",
        targets=(target,),
    )
    assert profile.to_dict()["targets"][0]["id"] == "t"
    assert profile.fingerprint() == profile.fingerprint()
    assert target.to_dict()["urls"] == ["/page"]
    assert target.fingerprint() == target.fingerprint()
    with pytest.raises(KeyError, match="unknown"):
        profile.target("missing")
    corpus = PreparedCorpus.from_dict(
        {
            "profile_id": "p",
            "profile_name": "Profile",
            "target_id": "t",
            "skill_name": "Skill",
            "warnings": ["warning"],
            "pages": [
                {
                    "url": "https://example.org/page",
                    "title": "Page",
                    "headings": ["Heading"],
                    "text": "Text",
                    "links": [],
                    "truncated": True,
                    "fetched_at": "now",
                    "final_url": "https://example.org/page",
                    "content_sha256": "hash",
                }
            ],
        }
    )
    assert corpus.pages[0].truncated
    assert "warning" in corpus.warnings
    assert (
        corpus.generation_payload(include_retrieval=True)["pages"][0]["fetched_at"]
        == "now"
    )
    assert corpus.fingerprint() != corpus.fingerprint(include_retrieval=True)
    assert (
        PreparedCorpus.from_dict(corpus.to_payload()).pages[0].content_sha256 == "hash"
    )


def test_model_edge_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        ExtractionConfig.from_mapping({"max_chars_per_page": 0})
    with pytest.raises(ValueError, match="positive"):
        CrawlConfig.from_mapping({"max_pages": 0})
    with pytest.raises(ValueError, match="non-negative"):
        CrawlConfig.from_mapping({"max_depth": -1})
    with pytest.raises(ValueError, match="max_redirects"):
        CrawlConfig.from_mapping({"max_redirects": -1})
    with pytest.raises(ValueError, match="positive"):
        TargetSpec.from_mapping({"id": "t", "max_pages": 0})
    with pytest.raises(ValueError, match="request_timeout"):
        CrawlConfig.from_mapping({"request_timeout_seconds": 0})
    with pytest.raises(ValueError, match="min_delay"):
        CrawlConfig.from_mapping({"min_delay_seconds": -1})
    with pytest.raises(ValueError, match="max_response"):
        CrawlConfig.from_mapping({"max_response_bytes": 0})
    with pytest.raises(ValueError, match="target.id"):
        TargetSpec.from_mapping({"name": "No id"})
    with pytest.raises(ValueError, match="base_url"):
        SourceProfile(id="bad", name="Bad", base_url="not-a-url")
    with pytest.raises(ValueError, match="safe directory"):
        SourceProfile(
            id="bad-area", name="Bad", base_url="https://example.org", area="../unsafe"
        )
    with pytest.raises(ValueError, match="safe directory"):
        SourceProfile(
            id="bad-area", name="Bad", base_url="https://example.org", area="..."
        )
    with pytest.raises(ValueError, match="safe directory"):
        SourceProfile(
            id="bad-area", name="Bad", base_url="https://example.org", area=" "
        )


def test_skill_draft_validation_and_metadata() -> None:
    with pytest.raises(ValueError, match="requires"):
        SkillDraft.from_mapping(
            {"name": "", "description": "", "body": ""},
            default_name="Default",
            source_urls=(),
            generator="test",
        )
    draft = SkillDraft.from_mapping(
        {
            "description": "A default skill",
            "body": "# Body",
            "metadata": {"from_value": True},
        },
        default_name="Default",
        source_urls=("https://example.org",),
        generator="test",
        metadata={"from_call": True},
    )
    assert draft.name == "Default"
    assert draft.metadata == {"from_call": True, "from_value": True}
    restored = SkillDraft.from_payload(draft.to_payload())
    assert restored == draft
    with pytest.raises(ValueError, match="generator"):
        SkillDraft.from_payload({"name": "x", "description": "x", "body": "x"})
    with pytest.raises(ValueError, match="metadata"):
        SkillDraft.from_payload(
            {
                "name": "x",
                "description": "x",
                "body": "x",
                "generator": "x",
                "metadata": [],
            }
        )


def test_bundle_record_reads_old_envelopes_with_defaults() -> None:
    """Older persisted bundles predate the refresh-integrity fields; they
    must load with defaults instead of failing cache reads."""
    page = PageRecord(
        requested_url="https://example.org/",
        final_url="https://example.org/",
        canonical_url=None,
        status_code=200,
        title="t",
        headings=(),
        text="body",
        links=(),
        fetched_at="now",
        content_sha256="hash",
    )
    bundle = BundleRecord(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name="S",
        pages=(page,),
        created_at="now",
    )
    payload = bundle.to_dict()
    payload.pop("absent_urls")
    payload.pop("incomplete")
    restored = BundleRecord.from_dict(payload)
    assert restored.absent_urls == ()
    assert restored.incomplete is False
    marked = BundleRecord.from_dict(
        {
            **bundle.to_dict(),
            "absent_urls": ["https://example.org/gone"],
            "incomplete": True,
        }
    )
    assert marked.absent_urls == ("https://example.org/gone",)
    assert marked.incomplete is True
