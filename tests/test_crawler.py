from __future__ import annotations

import pytest

from skillarum.crawler import CrawlError, WebsiteCrawler
from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec


def make_profile(
    base_url: str, *, robots: bool = False, follow: bool = False
) -> SourceProfile:
    return SourceProfile(
        id="fixture",
        name="Fixture Site",
        base_url=base_url,
        crawl=CrawlConfig(
            respect_robots=robots,
            allow_private_hosts=True,
            follow_links=follow,
            max_pages=10,
            max_depth=2,
            max_response_bytes=100_000,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )


def test_crawler_extracts_content_and_filters_external_links(
    fixture_server: str,
) -> None:
    profile = make_profile(fixture_server)
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
    assert len(bundle.pages) == 1
    page = bundle.pages[0]
    assert page.title == "Fixture Page"
    assert "Useful source text." in page.text
    assert "noise" not in page.text
    assert page.canonical_url == f"{fixture_server}/page"
    assert page.links == (f"{fixture_server}/other",)
    assert page.content_sha256


def test_crawler_discovers_matching_bundle_pages(fixture_server: str) -> None:
    profile = make_profile(fixture_server, follow=True)
    target = TargetSpec(
        id="bundle",
        name="Bundle",
        urls=("/page",),
        include_patterns=("/*",),
        exclude_patterns=("/blocked",),
    )
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
    assert {page.title for page in bundle.pages} == {"Fixture Page", "Other Page"}


def test_crawler_respects_robots(fixture_server: str) -> None:
    profile = make_profile(fixture_server, robots=True)
    target = TargetSpec(id="blocked", name="Blocked", urls=("/blocked",))
    with WebsiteCrawler(profile) as crawler:
        try:
            crawler.crawl(target)
        except CrawlError as exc:
            assert "no pages" in str(exc)
        else:  # pragma: no cover - the assertion above is the expected path.
            raise AssertionError("robots.txt should block the target")


def test_crawler_rejects_non_html_and_unsafe_redirects(fixture_server: str) -> None:
    profile = make_profile(fixture_server)
    with WebsiteCrawler(profile) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(TargetSpec(id="json", name="JSON", urls=("/not-html",)))


def test_crawler_records_warnings_and_deduplicates_canonical_pages(
    fixture_server: str,
) -> None:
    profile = make_profile(fixture_server)
    target = TargetSpec(
        id="duplicates",
        name="Duplicates",
        urls=("/page", "/redirect", "/external-canonical", "/empty"),
    )
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
    assert len(bundle.pages) == 3
    assert any(page.canonical_url is None for page in bundle.pages)
    assert any(
        "no title" in warning for page in bundle.pages for warning in page.warnings
    )
    assert any(
        "no extracted text" in warning
        for page in bundle.pages
        for warning in page.warnings
    )
    assert any(event.get("status") == "redirect" for event in bundle.events)


def test_crawler_keeps_page_when_one_link_is_malformed(fixture_server: str) -> None:
    profile = make_profile(fixture_server)
    target = TargetSpec(id="malformed", name="Malformed", urls=("/page",))
    with WebsiteCrawler(profile) as crawler:
        original_parse = crawler._parse_page

        def parse_with_bad_link(requested_url, response, depth):
            response._content = response.content.replace(
                b"/other", b"http://example.com:bad/"
            )
            return original_parse(requested_url, response, depth)

        crawler._parse_page = parse_with_bad_link
        bundle = crawler.crawl(target)
    assert len(bundle.pages) == 1
    assert any(
        "invalid link ignored" in warning for warning in bundle.pages[0].warnings
    )


def test_target_prefix_matching_respects_path_boundaries(fixture_server: str) -> None:
    profile = make_profile(fixture_server)
    target = TargetSpec(id="prefix", name="Prefix", include_prefixes=("/wiki",))
    with WebsiteCrawler(profile) as crawler:
        assert crawler._target_allows(target, f"{fixture_server}/wiki/page", set())
        assert not crawler._target_allows(
            target, f"{fixture_server}/wikimedia/page", set()
        )


def test_crawler_rejects_unsafe_and_cross_origin_requests(fixture_server: str) -> None:
    profile = make_profile(fixture_server)
    with WebsiteCrawler(profile) as crawler:
        with pytest.raises(CrawlError, match="cross-origin"):
            crawler._request("http://127.0.0.1:1")
        with pytest.raises(CrawlError, match="cross-origin"):
            crawler._request("https://example.org/")

    public_profile = SourceProfile(
        id="public",
        name="Public",
        base_url="https://example.org",
        crawl=CrawlConfig(),
        extraction=ExtractionConfig(),
        targets=(),
    )
    with WebsiteCrawler(public_profile) as crawler:
        with pytest.raises(CrawlError, match="unsafe"):
            crawler._request("http://127.0.0.1:1")


def test_crawler_handles_limits_and_invalid_selectors(fixture_server: str) -> None:
    limited = SourceProfile(
        id="limited",
        name="Limited",
        base_url=fixture_server,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_response_bytes=1,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )
    with WebsiteCrawler(limited) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))

    invalid_selector = make_profile(fixture_server)
    invalid_selector = SourceProfile(
        id="invalid",
        name="Invalid",
        base_url=fixture_server,
        crawl=invalid_selector.crawl,
        extraction=ExtractionConfig(main_selector="["),
        targets=(),
    )
    with WebsiteCrawler(invalid_selector) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(TargetSpec(id="page", name="Page", urls=("/page",)))

    no_redirects = SourceProfile(
        id="no-redirects",
        name="No Redirects",
        base_url=fixture_server,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_redirects=0,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )
    with WebsiteCrawler(no_redirects) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(
                TargetSpec(id="redirect", name="Redirect", urls=("/redirect",))
            )

    with WebsiteCrawler(make_profile(fixture_server)) as crawler:
        with pytest.raises(CrawlError, match="no pages"):
            crawler.crawl(
                TargetSpec(
                    id="excluded-start",
                    name="Excluded Start",
                    urls=("/blocked",),
                    exclude_patterns=("/blocked",),
                )
            )
        bundle = crawler.crawl(
            TargetSpec(
                id="request-limit",
                name="Request Limit",
                urls=("/not-html", "/page"),
                max_pages=1,
            )
        )
        assert len(bundle.pages) == 1
        assert any("not-html" in str(event) for event in bundle.events)


def test_crawler_classifies_absence_and_transient_failures(httpserver):
    """A definitive 404 is recorded as absent; a 500 is a transient failure
    that marks the bundle incomplete while a good page still anchors it."""
    base = httpserver.url_for("/")
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/ok").respond_with_data(
        "<html><head><title>OK</title></head><body><main><h1>OK</h1></main></body></html>",
        content_type="text/html",
    )
    httpserver.expect_request("/gone").respond_with_data(
        "missing", content_type="text/html", status=404
    )
    httpserver.expect_request("/broken").respond_with_data(
        "boom", content_type="text/html", status=500
    )
    profile = make_profile(base)
    target = TargetSpec(id="mixed", name="Mixed", urls=("/ok", "/gone", "/broken"))
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
    assert [page.title for page in bundle.pages] == ["OK"]
    assert bundle.incomplete is True
    assert bundle.absent_urls == (f"{base}gone",)
    with WebsiteCrawler(profile) as crawler2:
        clean_bundle = crawler2.crawl(
            TargetSpec(id="clean", name="Clean", urls=("/ok",))
        )
    assert clean_bundle.incomplete is False
    assert clean_bundle.absent_urls == ()
    with WebsiteCrawler(profile) as crawler3:
        with pytest.raises(CrawlError, match="no pages"):
            crawler3.crawl(TargetSpec(id="gone", name="Gone", urls=("/gone",)))


def test_crawler_decodes_undeclared_non_utf8_pages(httpserver):
    """A legacy page served as ISO-8859-1 with no charset declaration must
    not mojibake its text; the parser sniffs the body encoding instead of
    assuming UTF-8 with replacement characters."""
    base = httpserver.url_for("/")
    body = "<html><head><title>Café</title></head><body><main><h1>café</h1></main></body></html>"
    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/legacy").respond_with_data(
        body.encode("iso-8859-1"), content_type="text/html"
    )
    target = TargetSpec(id="legacy", name="Legacy", urls=("/legacy",))
    with WebsiteCrawler(make_profile(base)) as crawler:
        bundle = crawler.crawl(target)
    page = bundle.pages[0]
    assert page.title == "Café"
    assert "café" in page.text
    assert "\ufffd" not in page.text


def test_conditional_revalidation_enforces_byte_limit(httpserver):
    """Negative control: a cached body larger than the current configured
    byte limit must fail the replayed fetch instead of bypassing the bound."""
    from werkzeug.wrappers import Response

    base = httpserver.url_for("/")
    state = {"mode": "full"}

    def handler(_request):  # type: ignore[no-untyped-def]
        if state["mode"] == "revalidate":
            return Response(status=304)
        return Response(
            "<html><body><main>" + "y" * 4000 + "</main></body></html>",
            content_type="text/html",
            headers={"ETag": '"v1"'},
        )

    httpserver.expect_request("/page").respond_with_handler(handler)
    target = TargetSpec(id="page", name="Page", urls=("/page",))
    with WebsiteCrawler(make_profile(base)) as crawler:
        crawler.crawl(target)
        cache = dict(crawler.fetch_cache)
    state["mode"] = "revalidate"
    limited_profile = SourceProfile(
        id="limited",
        name="Limited",
        base_url=base,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_pages=10,
            max_response_bytes=100,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(),
    )
    with WebsiteCrawler(limited_profile, fetch_cache=cache) as crawler2:
        with pytest.raises(CrawlError, match="byte limit"):
            crawler2.crawl(target)


def test_conditional_revalidation_applies_to_redirect_hop(httpserver):
    """A redirect-resolved page must replay the stored validator on its
    final URL hop instead of always re-downloading the body."""
    from werkzeug.wrappers import Response

    base = httpserver.url_for("/")
    conditional_headers: list[dict[str, str]] = []

    def page_handler(request):  # type: ignore[no-untyped-def]
        conditional_headers.append(
            {
                key: value
                for key, value in request.headers.items()
                if key.lower() in {"if-none-match", "if-modified-since"}
            }
        )
        seen = request.headers.get("If-None-Match")
        if seen:
            return Response(status=304)
        return Response(
            "<html><body><main><h1>P</h1></main></body></html>",
            content_type="text/html",
            headers={"ETag": '"v1"'},
        )

    httpserver.expect_request("/robots.txt").respond_with_data(
        "User-agent: *\nAllow: /", content_type="text/plain"
    )
    httpserver.expect_request("/r").respond_with_data(
        b"", content_type="text/html", status=302, headers={"Location": "/p"}
    )
    httpserver.expect_request("/p").respond_with_handler(page_handler)
    profile = make_profile(base)
    target = TargetSpec(id="r", name="R", urls=("/r",))
    with WebsiteCrawler(profile) as crawler:
        bundle = crawler.crawl(target)
        assert bundle.pages[0].revalidated is False
        cache = dict(crawler.fetch_cache)
    conditional_headers.clear()
    with WebsiteCrawler(profile, fetch_cache=cache) as crawler2:
        bundle2 = crawler2.crawl(target)
    assert bundle2.pages[0].revalidated is True
    assert conditional_headers, "second run must reach the final URL"
    assert any(cond.get("If-None-Match") for cond in conditional_headers)
