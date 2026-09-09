from __future__ import annotations

from skillarum.models import BundleRecord, PageRecord
from skillarum.prepare import prepare_corpus


def test_prepare_truncates_and_deduplicates_warnings() -> None:
    page = PageRecord(
        requested_url="https://example.org/page",
        final_url="https://example.org/page",
        canonical_url=None,
        status_code=200,
        title="Page",
        headings=(),
        text="0123456789",
        links=(),
        fetched_at="now",
        content_sha256="hash",
        warnings=("existing",),
    )
    bundle = BundleRecord(
        profile_id="p",
        profile_name="P",
        target_id="t",
        skill_name="T",
        pages=(page,),
        created_at="now",
        warnings=("existing",),
    )
    corpus = prepare_corpus(bundle, max_chars_per_page=5)
    assert corpus.pages[0].text == "01234"
    assert corpus.pages[0].truncated
    assert corpus.pages[0].requested_url == page.requested_url
    assert corpus.pages[0].content_sha256 == "hash"
    assert corpus.warnings.count("existing") == 1
