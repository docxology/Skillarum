"""Index-derived profiles, block-preserving extraction, and authored descriptions."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest
import yaml
from conftest import _single_route_server

from skillarum.cli import main
from skillarum.config import load_profile
from skillarum.crawler import CrawlError, WebsiteCrawler
from skillarum.index_profile import (
    IndexEntry,
    build_index_profile,
    parse_index,
    targets_from_entries,
)
from skillarum.models import (
    CrawlConfig,
    ExtractionConfig,
    GenerationConfig,
    SourceProfile,
    TargetSpec,
)
from skillarum.pipeline import run_profile
from skillarum.render import validate_skill_file

ROOT = Path(__file__).resolve().parents[1]

INDEX_HTML = b"""<html><head><title>Site. | Research / Index</title></head><body>
<nav><a href='/wiki/Research/NavOnly'>nav</a></nav>
<div id='wikitext'>
<p><strong><a href='/wiki/Research/Intro'>Intro</a></strong></p>
<ul><li><a href='/wiki/Research/Index'>Index</a></li>
<li><a href='/wiki/Research/Alpha'>Alpha Page</a>, <a href='/wiki/Research/Beta'>Beta</a></li>
<li><a href='/wiki/Research/Alpha#part'>Alpha again</a></li>
<li><a href='/wiki/Research/Gamma?action=edit'>edit</a></li>
<li><a href='/wiki/Other/Delta'>outside prefix</a></li>
<li><a href='https://example.org/wiki/Research/Far'>cross origin</a></li>
<li><a href='#top'>top</a></li></ul>
<h2>Second Section</h2>
<ul><li><a href='/wiki/Research/Vid%C5%ABnas'>Vid\xc5\xabnas</a></li>
<li><a href='/wiki/Research/Beta'>Beta duplicate</a></li></ul>
</div></body></html>"""

PAGE_HTML = (
    b"<html><head><title>Site. | Research / Alpha</title></head><body>"
    b"<div id='wikitext'><h1>Alpha</h1><p>First\nparagraph <b>bold</b>.</p>"
    b"<ul><li>one</li><li>two<br>three</li></ul><pre>keep\nlines</pre></div>"
    b"</body></html>"
)


@pytest.fixture
def index_server() -> Iterator[str]:
    routes = {
        "/robots.txt": (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        "/wiki/Research/Index": (200, "text/html", INDEX_HTML),
        "/wiki/Research/Alpha": (200, "text/html", PAGE_HTML),
        "/wiki/Research/Json": (200, "application/json", b"{}"),
        "/wiki/Research/Missing": (404, "text/plain", b"gone"),
    }
    yield from _single_route_server(routes)


def _profile(base_url: str, **extraction: object) -> SourceProfile:
    return SourceProfile(
        id="fixture",
        name="Fixture Wiki",
        base_url=f"{base_url}/wiki/",
        area="Fixture",
        crawl=CrawlConfig(allow_private_hosts=True, max_pages=10, max_depth=0),
        extraction=ExtractionConfig(main_selector="#wikitext", **extraction),
        targets=(TargetSpec(id="seed", name="Seed", urls=("/wiki/Research/Alpha",)),),
    )


def test_parse_index_keeps_order_sections_and_filters_non_pages() -> None:
    entries = parse_index(
        INDEX_HTML,
        page_url="https://wiki.test/wiki/Research/Index",
        prefix="/wiki/Research/",
        main_selector="#wikitext",
    )
    names = [entry.page_name for entry in entries]
    assert names == ["Intro", "Index", "Alpha", "Beta", "Vidunas"]
    by_name = {entry.page_name: entry for entry in entries}
    assert by_name["Intro"].section == "Intro"
    assert by_name["Alpha"].section == "Intro"
    assert by_name["Alpha"].label == "Alpha Page"
    assert by_name["Vidunas"].section == "Second Section"
    # The first listing of Beta wins; the later duplicate is ignored.
    assert by_name["Beta"].section == "Intro"
    without_self = parse_index(
        INDEX_HTML,
        page_url="https://wiki.test/wiki/Research/Index",
        prefix="/wiki/Research/",
        main_selector="#wikitext",
        include_self=False,
    )
    assert "Index" not in [entry.page_name for entry in without_self]


def test_targets_are_unique_and_descriptions_are_portable() -> None:
    entries = [
        IndexEntry("https://wiki.test/wiki/R/Same", "Same <b>", "S"),
        IndexEntry("https://wiki.test/wiki/X/Same", "Same", ""),
    ]
    targets = targets_from_entries(
        entries,
        profile_name="Wiki",
        index_url="https://wiki.test/wiki/R/Index",
        id_prefix="r",
        name_prefix="R-",
    )
    assert [t["id"] for t in targets] == ["r-same", "r-same-2"]
    assert [t["name"] for t in targets] == ["R-Same", "R-Same-2"]
    assert all("<" not in t["description"] for t in targets)
    assert all(len(t["description"]) <= 1024 for t in targets)
    assert targets[0]["section"] == "S" and "section" not in targets[1]


def test_build_index_profile_loads_and_raises_budgets(tmp_path: Path) -> None:
    base = _profile("https://wiki.test")
    entries = [
        IndexEntry(f"https://wiki.test/wiki/Research/P{i}", f"P{i}", "S")
        for i in range(30)
    ]
    data = build_index_profile(
        base,
        entries,
        index_url="https://wiki.test/wiki/Research/Index",
        index_sha256="0" * 64,
        retrieved_at="2026-10-09T00:00:00+00:00",
        profile_id="derived",
        id_prefix="research",
        name_prefix="Research-",
        title_separator=" | ",
    )
    path = tmp_path / "derived.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    profile = load_profile(path)
    assert len(profile.targets) == 30
    assert profile.crawl.max_pages >= 30 and profile.crawl.max_requests >= 90
    assert profile.extraction.preserve_blocks
    assert profile.extraction.title_separator == " | "
    assert profile.targets[0].description.startswith("Source-grounded reference")
    assert data["derived_from"]["entry_count"] == 30


def test_cli_profile_from_index_live_fixture_and_saved_html(
    index_server: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base_path = tmp_path / "base.yaml"
    base_path.write_text(
        yaml.safe_dump(
            {
                "id": "fixture",
                "name": "Fixture Wiki",
                "base_url": f"{index_server}/wiki/",
                "area": "Fixture",
                "crawl": {"allow_private_hosts": True},
                "extraction": {"main_selector": "#wikitext"},
                "targets": [{"id": "seed", "urls": ["/wiki/Research/Alpha"]}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "derived.yaml"
    args = [
        "profile-from-index",
        "--profile",
        str(base_path),
        "--index-url",
        f"{index_server}/wiki/Research/Index",
        "--prefix",
        "/wiki/Research/",
        "--output",
        str(out),
        "--profile-id",
        "derived",
        "--id-prefix",
        "research",
        "--name-prefix",
        "Research-",
        "--title-separator",
        " | ",
    ]
    assert main([*args, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entry_count"] == 5
    assert payload["sections"] == ["Intro", "Second Section"]
    assert out.read_text(encoding="utf-8").startswith("# Generated by")
    assert len(load_profile(out).targets) == 5

    saved = tmp_path / "index.html"
    saved.write_bytes(INDEX_HTML)
    assert main([*args, "--html", str(saved)]) == 0
    assert "5 targets written" in capsys.readouterr().out

    empty = tmp_path / "empty.html"
    empty.write_bytes(b"<html><body><div id='wikitext'></div></body></html>")
    assert main([*args, "--html", str(empty), "--json"]) != 0


def test_fetch_raw_rejects_non_html_and_errors(index_server: str) -> None:
    profile = _profile(index_server)
    with WebsiteCrawler(profile) as crawler:
        content, final_url = crawler.fetch_raw(f"{index_server}/wiki/Research/Index")
        assert content == INDEX_HTML
        assert final_url.endswith("/wiki/Research/Index")
        with pytest.raises(CrawlError, match="non-HTML"):
            crawler.fetch_raw(f"{index_server}/wiki/Research/Json")
        with pytest.raises(CrawlError, match="HTTP 404"):
            crawler.fetch_raw(f"{index_server}/wiki/Research/Missing")


def test_block_extraction_and_title_cleaning(index_server: str) -> None:
    flat = _profile(index_server)
    blocks = _profile(index_server, preserve_blocks=True, title_separator=" | ")
    target = flat.targets[0]
    with WebsiteCrawler(flat) as crawler:
        flat_page = crawler.crawl(target).pages[0]
    with WebsiteCrawler(blocks) as crawler:
        block_page = crawler.crawl(target).pages[0]
    assert flat_page.title == "Site. | Research / Alpha"
    assert "\n\n" not in flat_page.text
    assert block_page.title == "Research / Alpha"
    assert block_page.text.split("\n\n") == [
        "Alpha",
        "First paragraph bold .",
        "one",
        "two\nthree",
        "keep\nlines",
    ]


def test_opt_in_fields_do_not_change_legacy_fingerprints() -> None:
    legacy = _profile("https://wiki.test")
    data = legacy.to_dict()
    assert "preserve_blocks" not in data["extraction"]
    assert "title_separator" not in data["extraction"]
    assert "description" not in data["targets"][0]
    assert "description" not in legacy.targets[0].to_dict()
    refined = _profile("https://wiki.test", preserve_blocks=True)
    assert refined.fingerprint() != legacy.fingerprint()
    assert ExtractionConfig(title_separator=" | ").clean_title("no separator") == (
        "no separator"
    )
    assert ExtractionConfig(title_separator=" | ").clean_title("A | ") == "A | "


def test_target_description_is_authoritative_in_frontmatter(
    index_server: str, tmp_path: Path
) -> None:
    description = "Authored description for the Alpha page; cite its URL."
    profile = SourceProfile(
        id="fixture",
        name="Fixture Wiki",
        base_url=f"{index_server}/wiki/",
        area="Fixture",
        crawl=CrawlConfig(allow_private_hosts=True, max_pages=10, max_depth=0),
        extraction=ExtractionConfig(main_selector="#wikitext", preserve_blocks=True),
        targets=(
            TargetSpec(
                id="alpha",
                name="Alpha",
                urls=("/wiki/Research/Alpha",),
                description=description,
            ),
        ),
    )
    (skill_path,) = run_profile(profile, output_dir=tmp_path, backend="deterministic")
    metadata = validate_skill_file(skill_path)
    assert metadata["description"] == description
    manifest = json.loads((skill_path.parent / "manifest.json").read_text())
    assert manifest["metadata"]["generator_description"].startswith(
        "Source-grounded reference skill"
    )
    # A second run reuses the cached draft and keeps the authored description.
    (again,) = run_profile(profile, output_dir=tmp_path, backend="deterministic")
    assert validate_skill_file(again)["description"] == description


def test_cube_skill_checker_and_frontmatter() -> None:
    skill = ROOT / "skills" / "math4wisdom-cube"
    result = subprocess.run(
        [sys.executable, str(skill / "scripts" / "verify_combinatorics.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    ids = [check["id"] for check in report["checks"]]
    assert report["ok"] and len(ids) == 23
    assert set(ids) == {f"M{i}" for i in range(1, 24)}
    metadata = validate_skill_file(skill / "SKILL.md")
    assert metadata["name"] == "math4wisdom-cube"
    assert metadata["metadata"]["version"]
    assert "<" not in metadata["description"] and len(metadata["description"]) <= 1024
    for reference in (
        "sources.md",
        "mathematics.md",
        "interpretations.md",
        "investigator-protocol.md",
        "blind-brief.md",
    ):
        assert (skill / "references" / reference).is_file()


def test_cube_transverse_negative_controls() -> None:
    ns = runpy.run_path(
        str(ROOT / "skills/math4wisdom-cube/scripts/verify_combinatorics.py")
    )
    triples = ns["transverse_triples"]()
    flags = [
        (v, e, f)
        for v in ns["VERTICES"]
        for e in ns["EDGES"]
        for f in ns["FACES"]
        if v in e and e <= f
    ]
    for damaged in (triples[:-1], triples[:-1] + [triples[0]], flags, flags[:24]):
        results = []
        ns["transverse_checks"](results, damaged)
        assert results[0]["id"] == "M22" and not results[0]["ok"]


def test_cube_sl3_dimension_preserving_negative_control() -> None:
    ns = runpy.run_path(
        str(ROOT / "skills/math4wisdom-cube/scripts/verify_combinatorics.py")
    )
    groupings = ns["sl3_groupings"]()
    left, right = groupings["vector"]
    a, b = ("W", (1,)), ("dual", (1,))
    left.remove(a)
    right.remove(b)
    left.add(b)
    right.add(a)
    assert [len(left), len(right)] == [4, 4]
    results = []
    ns["sl3_checks"](results, groupings)
    assert not results[0]["ok"]
    assert not results[0]["evidence"]["invariant_blocks"]


def test_cube_checker_cli_rejects_incomplete_transverse_set(tmp_path: Path) -> None:
    source = ROOT / "skills/math4wisdom-cube/scripts/verify_combinatorics.py"
    text = source.read_text(encoding="utf-8")
    original = "    transverse_checks(results)\n"
    assert text.count(original) == 1
    altered = tmp_path / "damaged_checker.py"
    altered.write_text(
        text.replace(
            original, "    transverse_checks(results, transverse_triples()[:-1])\n"
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(altered)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert not report["ok"]
    assert [c["id"] for c in report["checks"] if not c["ok"]] == ["M22"]


def test_block_extraction_never_emits_comments_or_scripts() -> None:
    from bs4 import BeautifulSoup

    from skillarum.crawler import _block_text

    html = (
        "<div><p>a<!-- hidden\nmulti --> b</p>"
        "<script>var x =\n1;</script><p>c</p></div>"
    )
    root = BeautifulSoup(html, "html.parser").div
    flat = BeautifulSoup(html, "html.parser").div.get_text(" ", strip=True)
    text = _block_text(root)
    assert "hidden" not in text and "hidden" not in flat
    # Without a remove_selectors entry for script, both paths keep script
    # text; the block path must not add anything the flat path omits.
    assert set(text.split()) <= set(flat.split())


def test_index_profile_keeps_base_user_agent_and_generation(tmp_path: Path) -> None:
    base = SourceProfile(
        id="base",
        name="Base",
        base_url="https://wiki.test/wiki/",
        crawl=CrawlConfig(user_agent="MyBot/1 (me@example.org)"),
        generation=GenerationConfig(
            backend="ollama",
            fallback_backend="deterministic",
            ollama_url="http://10.0.0.5:11434",
            ollama_num_ctx=4096,
        ),
        targets=(TargetSpec(id="seed", name="Seed", urls=("/wiki/A",)),),
    )
    data = build_index_profile(
        base,
        [IndexEntry("https://wiki.test/wiki/R/P", "P", "")],
        index_url="https://wiki.test/wiki/R/Index",
        index_sha256="0" * 64,
        retrieved_at="2026-10-09T00:00:00+00:00",
        profile_id="derived",
        id_prefix="r",
        name_prefix="R-",
    )
    path = tmp_path / "derived.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    derived = load_profile(path)
    assert derived.crawl.user_agent == "MyBot/1 (me@example.org)"
    assert derived.generation.fallback_backend == "deterministic"
    assert derived.generation.ollama_url == "http://10.0.0.5:11434"
    assert derived.generation.ollama_num_ctx == 4096


def test_prefix_matches_on_segment_boundary_and_names_are_safe() -> None:
    html = (
        b"<div id='w'><a href='/wiki/A'>A</a><a href='/wikipedia/Z'>Z</a>"
        b"<a href='/wiki/%0Aevil'>e</a><a href='/wiki/Foo%2FBar'>f</a></div>"
    )
    entries = parse_index(
        html,
        page_url="https://wiki.test/wiki/Index",
        prefix="/wiki",
        main_selector="#w",
    )
    assert all("/wikipedia/" not in entry.url for entry in entries)
    names = [entry.page_name for entry in entries]
    assert names == ["A", "evil", "Foo-Bar"]


def test_long_or_bracketed_labels_are_clipped_in_descriptions() -> None:
    entry = IndexEntry("https://wiki.test/wiki/R/P", "L" * 500 + '<x>"q"', "S" * 300)
    (target,) = targets_from_entries(
        [entry],
        profile_name="Wiki",
        index_url="https://wiki.test/wiki/R/Index",
        id_prefix="r",
        name_prefix="R-",
    )
    assert "<" not in target["description"] and ">" not in target["description"]
    assert len(target["description"]) < 600
    assert len(target["section"]) <= 80


def test_authored_descriptions_are_validated() -> None:
    with pytest.raises(ValueError, match="angle brackets"):
        TargetSpec.from_mapping({"id": "a", "urls": ["/x"], "description": "<b>x</b>"})
    with pytest.raises(ValueError, match="exceeds"):
        TargetSpec.from_mapping({"id": "a", "urls": ["/x"], "description": "x" * 1025})
    assert TargetSpec.from_mapping(
        {"id": "a", "urls": ["/x"], "description": " two\n words "}
    ).description == ("two words")


def test_saved_html_index_must_match_profile_origin(tmp_path: Path) -> None:
    from skillarum.index_profile import write_index_profile

    saved = tmp_path / "index.html"
    saved.write_bytes(INDEX_HTML)
    with pytest.raises(ValueError, match="outside the profile origin"):
        write_index_profile(
            _profile("https://wiki.test"),
            index_url="https://elsewhere.test/wiki/Research/Index",
            prefix="/wiki/Research/",
            output=tmp_path / "out.yaml",
            profile_id="derived",
            id_prefix="r",
            name_prefix="R-",
            html_path=saved,
        )
