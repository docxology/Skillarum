# Refreshing source websites and installed skills

The seven configured skills and a broad website inventory are different outputs.
The profiles under `data/sources/` define small, reviewable page bundles. The
`snapshot-site` command inventories public static HTML and retains raw responses;
it does not load prior response or bundle caches. It does not compile hundreds
of pages into an oversized skill.

## Empty-cache skill acquisition

Start in an empty output directory. Moving the previous generated output aside
preserves historical evidence while removing it from active cache lookup and
evaluation. Choose an unused dated backup name before running this sequence:

```bash
mv output output-before-refresh
uv run python -m skillarum evaluate \
  --profile data/sources/active_inference_institute.yaml \
  --profile data/sources/math4wisdom.yaml \
  --live --refresh --backend deterministic --output-dir output --json
```

The move is unnecessary for a first acquisition with no `output/`. Do not merge
old `runs/`, `.cache/`, or generated skills back into the fresh output. A later
`--live` flag cannot convert old records to live evidence. Within a new multi-target
run, the fetcher may revalidate shared pages; the per-page receipts distinguish
that activity from reuse of an earlier acquisition.

## Broader website inventory

These commands use the current Institute sitemap and a query-free Math4Wisdom
link crawl. Every destination must be empty. The flags are:

|Flag|Meaning|
| --- | --- |
|`--archive PATH`|After the crawl, verify raw receipts and write one deterministic `.tar.gz` archive plus an adjacent JSON summary bound to the archived receipt. Existing archives are never overwritten.|
|`--archive-only`|Verify and archive an already captured directory without network requests; requires `--archive`.|
|`--max-pages N`|Accepted-page cap for the snapshot sweep (default 10000).|
|`--max-requests N`|Total request cap including pages, redirects, robots, and retries (default 20000).|

The crawl also respects robots rules, response size limits, and a minimum
delay of 0.25 seconds.

```bash
uv run python -m skillarum snapshot-site \
  --profile data/sources/active_inference_institute.yaml \
  --sitemap https://activeinference.institute/sitemap.xml \
  --output-dir output/site_snapshots/active-inference-institute \
  --archive output/source_archives/active-inference-institute.tar.gz --json

uv run python -m skillarum snapshot-site \
  --profile data/sources/math4wisdom.yaml \
  --seed https://www.math4wisdom.com/ \
  --seed https://www.math4wisdom.com/wiki/Site/AllRecentChanges \
  --seed https://www.math4wisdom.com/wiki/Exposition/Introduction \
  --seed https://www.math4wisdom.com/wiki/Research/Index \
  --output-dir output/site_snapshots/math4wisdom \
  --archive output/source_archives/math4wisdom.tar.gz --json
```

`scripts/rescrape_sites.py` is an equivalent thin entry point to `snapshot-site`.
Existing archives are never overwritten.

`snapshot.json` records the acquisition window, seeds, exact scope, accepted
pages, discovered URLs, unresolved URLs, malformed discovery URLs, request
count, warnings, and limits. One malformed sitemap or seed URL does not abort
the sweep; it is listed under `invalid_urls` and fails completeness explicitly.
The command exits **1** whenever that strict inventory is incomplete, including
rejected attachments. This is a diagnostic result to inspect, not a failure to
hide. A `.tar.gz` and its adjacent JSON summary can still preserve the completed
portion. The archive summary is bound to the archived receipt — completeness is
re-derived from the archived pages when the summary is loaded, so an edited
summary cannot promote an incomplete acquisition — and `research build` checks
it before using its counts in the manuscript.

## Refresh semantics for skill bundles

`--refresh` re-crawls the configured targets with fresh page data while the
conditional fetch cache still avoids re-downloading unchanged bytes. A refresh
crawl that loses previously-present pages without definitive evidence they are
gone (transient failures, robots rejections, or exhausted limits) is recorded
as degraded in the run manifest (`refresh_degraded`), and the previous cached
bundle is retained instead of being replaced. A page observed with HTTP 404 or
410 is definitive absence: the deletion propagates into the refreshed cache
and `refresh_diff` records the removal either way. Bundle records carry
`absent_urls` and an `incomplete` flag so consumers can distinguish a real
shrinkage from a truncated crawl.

A sitemap proves coverage only of the declared URL list. Link traversal covers
only same-origin, query-free HTML reachable through the extraction boundary.
Neither proves coverage of unlinked, private, dynamically rendered, or non-HTML
content. Raw archives remain local and outside the publication allowlist.

## Regenerate publication and replace active skills

```bash
uv run --extra research python -m skillarum research build --output-dir output --json
uv run python -m skillarum install \
  output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
uv run python -m skillarum drift \
  output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
```

Repeat installation and drift verification for each refreshed package. Installation
validates and stages the complete package under a lock, then replaces the directory
named by its portable frontmatter slug. An old file omitted from the new package
is removed by that replacement. Other skills in the harness root are unaffected.
Retain the installation receipts with the refresh report.

Render and validate the manuscript through the sibling template only after the
research build succeeds. The render hook runs the offline research build again
so charts, captions, site inventory counts, and manuscript variables use the same
current evidence.
