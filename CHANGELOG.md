# Changelog

All notable changes to Skillarum are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Declared dependency floors now match the versions the lockfile already
  resolves: `beautifulsoup4>=4.13`, `httpx>=0.28`, `pyyaml>=6.0.2`,
  `openai>=2.0`, `matplotlib>=3.10`, `pytest>=8.3`, `coverage[toml]>=7.15`,
  and `ruff>=0.15`. No resolved version, runtime behavior, or public contract
  changes; `uv lock` remains valid.

### Fixed
- `docs/release-checklist.md` no longer instructs readers to pass the
  historical `working/Skillarum` path to the parent renderer and validator.
  The path is workspace-owned and now appears as a placeholder, with the dated
  evidence for the path that resolved recorded in
  `docs/investigations/2026-10-12-synesis/validation.md`. The parent signpost
  item records that `scripts/check_signposts.py` is absent from the current
  template and sidecar.
- `docs/extending.md` described this checkout as a private sidecar; it is the
  standalone public `docxology/Skillarum` project.

## [0.3.1] - 2026-10-09

Correction release. Version DOI `10.5281/zenodo.23271010`.

### Fixed
- `math4wisdom-cube` 0.3.0: withdraws the 0.2.0 note that 1+3+3+1 is the
  generic grading pattern, which was adopted from an investigator report
  without recomputation and is false; new check M21 (21 checks).
- The 0.3.0 entry below said the cube investigators came from three model
  vendors. Two of the three ran on Claude; the entry now says so, matching the
  investigation record.
- README: 527 of the 528 Research descriptions name an index section;
  `Research-Introduction` precedes the first heading.
- `docs/publication.md` described the 0.2.0 CITATION.cff DOI layout.

### Changed
- The manuscript's investigation case study records the post-audit
  correction.

## [0.3.0] - 2026-10-09

### Added
- **`profile-from-index` command** (`src/skillarum/index_profile.py`) - derives one
  exact-page target per link listed on a site's own index page, keeps the
  index's section grouping, writes authored descriptions, and records an index
  receipt (URL, retrieval time, SHA-256, entry count) under `derived_from`.
  The index page is fetched through the crawler (`WebsiteCrawler.fetch_raw`),
  so robots, origin, SSRF, and request-budget rules apply.
- **Math 4 Wisdom Research profile** (`data/sources/math4wisdom_research.yaml`) -
  528 targets, one per page listed on `Research/Index`, grouped into 42 index
  sections; rendered skills are committed under `output/skills/Math4Wisdom/`.
- **Opt-in extraction refinements** - `extraction.preserve_blocks` keeps
  paragraph, list, and heading boundaries; `extraction.title_separator` drops a
  site-wide title prefix. Both default off and are omitted from fingerprints
  when unset, so existing profiles keep their cache identities.
- **Authored target descriptions** - `targets[].description` is authoritative
  for the rendered frontmatter; the generator's own description is retained as
  `generator_description` in the manifest metadata.
- **`math4wisdom-cube` investigation skill** (`skills/math4wisdom-cube/`) -
  a versioned skill on the cube, its two tetrahedra, Wondrous Wisdom's three
  languages, and the proposed Spin(8) triality reading, with separate source,
  mathematics, interpretation, and test ledgers, a standard-library checker
  for every mathematical item, and an independent-investigator protocol.
- **Independent investigation record** (`docs/investigations/2026-10-09-cube/`) -
  three investigators in separate sessions (two on Claude models, one
  reporting OpenAI lineage) audited version 0.1.0 of the cube skill; their reports are kept verbatim and the 0.2.0 revision records
  what each finding changed.

### Changed
- `data/sources/math4wisdom.yaml` enables block-preserving extraction and title
  cleaning, adds authored descriptions to its three targets, and raises the
  polite request delay to 0.5 s.
- Generated `output/skills/` packages (deterministic backend) are now tracked as
  reviewable outputs; the rest of `output/` stays untracked.
- Recorded the Zenodo concept DOI `10.5281/zenodo.22663906`, read from the
  published 0.2.0 record.
- Per-target figures (generation latency, source overlap) draw only declared
  evaluation cases once there are more than 40 observations; captions state how
  many index-derived observations are counted only in area-level figures.
  Observations carry `metadata.declared_case`.
- Manuscript bindings separate profiles from source areas
  (`CONFIGURED_AREA_COUNT`), summarize large profiles as one table row, and add
  `INDEX_DERIVED_*` tokens.
- The publication-metadata test checks DOI agreement across `CITATION.cff`, the
  manuscript configuration, and the README instead of pinning one record.

### Fixed
- Block-preserving extraction no longer turns HTML comments or CDATA into
  visible text.
- Index-derived profiles keep the base profile's user agent and all generation
  options.
- Authored target descriptions are validated (no angle brackets, at most 1024
  characters); index labels and sections are clipped inside descriptions.
- `--prefix` matches on a path-segment boundary; decoded page names are reduced
  to `[A-Za-z0-9._-]`; a saved `--html` index must match the profile origin.

### Evidence
- All 538 completed observations (528 Research targets, 6 Math 4 Wisdom, 4
  Active Inference Institute) are live acquisitions; the Math 4 Wisdom profiles
  were re-acquired on 2026-10-09 with `evaluate --live --refresh`.

## [0.2.0] - 2026-09-08

### Added
- **Tutorial documentation** - Complete walkthrough from clone to first rendered skill installed in a harness
- **Architecture refresh** - Updated module documentation covering redaction, policies, install, evals, runtimes, serve, quarantine, mcp_server, and repo_source
- **Serve command** - Read-only HTTP discovery server exposing rendered skills via REST API
- **Repository-as-source ingestion** - Support for local git repositories as skill sources with commit-SHA provenance  
- **MCP stdio server** - Zero-dependency Model Context Protocol server for agent integration
- **Quarantine-then-promote** - Safety mechanism for refreshed drafts that differ from cached canonical versions
- **Cross-runtime frontmatter compilation** - Per-target field allowlists for claude, codex, and agentskills compatibility
- **Fixture evaluation gates** - Release-blocking numeric gates with dated baseline scorecard
- **Install manifest and drift detection** - Sidecar tracking for installed vs canonical skill comparison
- **Security policy packs** - Declarative regex-based validation for rendered skill content
- **Secret redaction** - Two-pass credential scrubbing with non-leakage verification gates

### Improved  
- **Documentation accuracy** - All command examples in AGENTS.md and README.md verified working
- **Test coverage** - Hermetic scholarship fixes and comprehensive edge case testing
- **Manuscript outputs** - Regenerated with updated figure captions and cross-references
- **Formal model** - Numbered display equations with proper cross-referencing
- **Security model** - Formal adversary model and fail-closed composition propositions

### Fixed
- **Manuscript restoration** - Restored the docs/manuscript/ directory
- **Unused locals cleanup** - Removed flagged variables in runtimes and quarantine modules
- **Citation synchronization** - Updated concurrent-work and intro context citations with verification

### Documentation
- Added complete tutorial covering doctor, pack, verify --policy security, install --harness claude, drift
- Refreshed architecture.md with new module responsibilities and trust boundaries  
- Verified all README.md and AGENTS.md command examples execute successfully
- Added comprehensive troubleshooting guidance for common issues

## Prior Releases

See git log for detailed commit history prior to formal changelog adoption.