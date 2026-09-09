# Skillarum agentic wave and release — 2026-09-08

This follow-up supersedes the implementation and verification counts in the
[initial review](review-2026-09-07.md) and the
[agentic revision](review-agentic-2026-09-07.md); those documents remain
historical records. All numbers below are receipts from the
post-freeze run recorded in
`output/reports/agentic-review-2026-09-08.json`, its render-ready v2 rerun,
the post-fix gate rerun, and the final
live-evidence release identity, produced by the release lane under Codex
delegation. Dates use America/Los_Angeles. The existing dirty
baseline was preserved throughout; nothing was reset, staged, committed, or
published.

**Status: final reconciliation against the live-evidence release
(2026-09-08).** The bounded polish wave landed, the provenance repair
landed, the user-authorized fresh live acquisition completed, and the
Figure 6 caption clarification (render #6, science PASS) is folded in; the
sections below carry the final receipts (suite 555 passed / 2 skipped /
92.14% — unchanged, caption-only delta; PDF `f3b3e1d8…`, report
`evaluation-af3c4e80`). The pre-polish receipt
`output/reports/agentic-review-2026-09-08.json` (08:28) remains the
F1–F23/H1–H4 disposition record; v2, post-fix, and render #5 gate tables
and identity hashes are historical, superseded by section 6.

## 1. Surface map

| Surface | Owning source | Delivered evidence |
| --- | --- | --- |
| Statistics and report semantics | `src/skillarum/statistics.py` (verified clean by oracle audit), `research.py` | Independent oracles to ≤5.4e-14 over 49 cases; strict boolean proportions; closed evidence-origin vocabulary; additive diagnostics |
| Figures and captions | `src/skillarum/figures.py` | 12-registry contract, source-hash rebinding, two visual repairs, determinism verified byte-identical across two runs |
| Manuscript bindings and build | `src/skillarum/manuscript.py`, `publication.py`, `cli.py` | Canonical table ordering, new offline tree gates, corrected attribution, 29-entry bibliography closure |
| Acquisition and package integrity | `site_snapshot.py`, `crawler.py`, `pipeline.py`, `urls.py`, `models.py`, `config.py`, `generators.py`, `render.py`, `redaction.py`, `quarantine.py`, `repo_source.py` | 13 fixed defects each with a failing pre-fix control; bounded reads; refresh cache preservation |
| MCP and package lifecycle | `mcp_server.py`, `serve.py`, `install.py`, `runtimes.py`, `packdiff.py`, `signature.py`, `policies.py` | Initialized-session gate, traversal/duplicate/excerpt hardening, documented subset claim |
| General documentation | root `README.md`/`AGENTS.md`/`TODO.md`, `docs/`, directory guides | Precise side-effect boundaries, complete command table, extension recipes (`docs/extending.md`), no-mocks conventions |
| Current source corpus | `site_snapshot.py`, declared profiles | Dated Sept 8 full-site archives (AII 899/899; Math 890/1228 with 338 persistent unresolved) plus the fresh live re-acquisition of all 7 configured targets: 30/30 selected pages hash-unchanged against the archives (recorded, never assumed) |
| Scholarship | `data/claims.yaml` (12 claims), `data/citations.yaml` (29 entries) | All ledgers resolve; adoption-attribution claim registered |
| Verification | shared locked venv (Python 3.12.13, pytest 9.1.1, ruff 0.15.21, coverage 7.15.1) | Gates 1–8 with exits; 15/15 security probes; independent artifact audit; science full QA PASS |

## 2. Issues found and fixed

Twenty-seven finding items were dispositioned across six build lanes and two
audit lanes. Every "fixed" row below has a reproduced pre-fix failure and a
negative control that failed before the fix and passed after.

| Finding | Disposition | Owner |
| --- | --- | --- |
| F1–F4 | Figures-layer defects fixed with negative controls; `source-overlap` figure shipped with 28/28 exact-match against independent recomputation | figures lane |
| F5 | `prop:index-soundness` justification corrected to fail-closed abort + manifest enumeration | manuscript lane |
| F6 | Abstract rate statement made conditional on run completion | manuscript lane |
| F7 | Greshake et al. corrected to ACM AiSec 2023 with DOI 10.1145/3605764.3623985 (CrossRef-verified; prior USENIX claim was wrong) | manuscript lane |
| F8 (MAJOR) | Adoption lineage cited in Related Work; `claim-adoption-attribution` registered in `data/claims.yaml` | manuscript lane |
| F9, F10 | Equation cross-references and backend/telemetry context corrected | manuscript lane |
| F11–F13 | Ledger entries added/corrected; RFC 9309 authors expanded; 1:1 bib↔citations closure (29/29) | manuscript lane |
| F14 | `doctor --no-network` help now states the writeability check still runs and creates `output/.cache`; behavior test added | manuscript lane (found by the docs lane) |
| F15 | `install.py` drift docstring documents all eight issue codes including `installed_package_drift` | integrations lane (found by the docs lane) |
| F16 | `docs/source-refresh.md` documents `snapshot-site --archive/--archive-only/--max-pages/--max-requests` | acquisition lane (found by the docs lane) |
| F17 | Install path traversal: `install.py` refuses non-portable frontmatter names before any write; probe R1a/R1b REFUTED, R1c SOUND control | integrations lane |
| F18 | UTF-16 sitemap DOCTYPE bypassed the byte-sniff guard → replaced with encoding-independent XML-declaration rejection (`_reject_xml_declarations`); probe r2c REFUTED | acquisition lane |
| F19 | Duplicate zip members escaped pack signatures; member manifest rejects duplicates, signing refuses them; probe REFUTED | integrations lane |
| F20 | Forged archive summary could flip completeness; loader re-derives completeness/unresolved/raw counts from archived receipts; probe r5 ERROR = rejection-before-return | acquisition lane |
| F21 | Policy excerpts echoed credential-shaped tokens; all excerpts redacted via `redact_secrets`, `hardcoded_secret` shows `<{secret}>` placeholder, offsets added; probe REFUTED | integrations lane (ownership adjudicated from the manuscript lane per Codex) |
| F22 | Pack digest computed before signature; digest now computed after `write_signature` with self-path/`.zip` exclusions reported in `excluded_archives`; probe REFUTED | manuscript lane |
| F23 | Case-variant private-path bypass (`data/Runs/x` → private `data/runs/x` on case-insensitive hosts); blocklists casefold parts; probe REFUTED | methods lane |
| H1 | Proxy environment could reroute acquisition; `trust_env=False` on the acquisition client (crawler.py:437), grep-verified in place | acquisition lane |
| H2 (r9a) | `_sanitize_error` kept plain `sk-…` API keys; pattern broadened + canonical redaction pass; probe REFUTED | acquisition lane (routed from the integrations lane) |
| H3 (r10) | Provider-generated `description` skipped the unsafe-instruction policy; enforcement moved to callers at generation, pipeline cache/trace loads, and render package gate; end-to-end subprocess test | acquisition lane (routed from the integrations lane) |
| H4 | `render.validate_skill_package` unbounded reads; `_read_bounded_text` + 16 MiB cap on all four package-validation reads; oversize-rejection test passes | acquisition lane (remainder routed from the integrations lane) |
| Non-finding hardening | MCP initialized-session state machine (`-32000` pre-init gate), spec-aligned `-32002`, bounded stdin framing, install destination confinement, refresh cache preservation on degraded crawls, IPv4-mapped IPv6 classification, 304/redirect revalidation, plus 12 further crawler/snapshot regressions | owning lanes as listed |

**Gate-5 promotion-by-design.** The first post-freeze `research build`
FAILED by design: the F20 loader correctly rejected the pre-wave 02:43Z
archive receipts (`parsed_html_responses` re-derivation mismatch). The
2026-09-08 candidate refresh was promoted after verification
under the new loader (AII complete=True 899/899; Math complete=False 890 with
documented unresolved scope); the previous canonical archives were
retention-renamed to `output/source_archives-before-refresh-20260908-1349/`,
and the full gate order was rerun. Four content-changed Math URLs intersect
no selected package page set, so no skill regeneration was needed.

**Source-overlap embed adjudication.** Option (b), registry-only this wave:
a hard `{{FIGURE_SOURCE_OVERLAP_CAPTION}}` token provably breaks the
non-owned fixture path (a 1-observation fixture registry cannot carry the
gated panel). The manuscript describes the panel conditionally, the registry
limitation states that the linkage is prose-only, and `docs/figures.md`
records the embed as a next-wave item. Nothing anticipatory remains silent.

**Polish wave (render-ready v2).** The bounded polish corrections landed and
were verified in the v2 gate rerun: bibliography accents fixed with
byte-verified umlauts; title braces landed (including the StoryOfThreeMinds,
NLU, OWASP, and React entries); the Attebury entry is dated **2026** in both
`docs/manuscript/references.bib` and `data/citations.yaml` from the
GitHub-created-at primary evidence; **F-A1 closed** — the registry now binds
all 12 figures with both PNG (`artifact_sha256`) and SVG (`vector_sha256`)
hashes (24 artifact bindings) plus 12 `source_sha256` report bindings, so
`source-overlap.png` (artifact hash `c7f1674b…`) is no longer unbound; Fig 5
and Fig 6 label/tick artifacts, the lone-"g." hyphen break, and the light
footnotes are fixed; an experimental preamble qualifier was surgically
undone to frozen bytes (freeze-watch clean). The DOI title page displays the authentic
reserved DOI; `docs/manuscript/config.yaml` and the release receipts record
its reserved/unpublished status, and the rendered text makes no publication
assertion. The on-disk publication manifest (09:59) predates the registry
fix and regenerates once more in the closing chain per the final-write rule.

**Provenance repair and live-evidence recapture (final).** A runtime repair
fixed a real render.py source-reference byte-hash mismatch and unchecked
references, removed a silent pipeline skip, and fixed two scholarship-test
failures; 15 new tests joined the suite (`test_source_reference_integrity.py`
plus `test_scholarship.py` additions). The source-reference contract is the
plain SHA-256 of the exact raw `sources.json` bytes, with no logical
serialization workaround. Runtime closed on four verified hashes
(`render.py e94cb5cd…`, `pipeline.py 8da41a2b…`,
`test_source_reference_integrity.py 1dd949d0…`, `test_scholarship.py
6fdc6b5e…`). Because the evaluate CLI does not forward `force_process`, the
root-authorized live acquisition used the documented pipeline Python API
(`run_profile_from_path` with `evidence_origin='live'`, `refresh=True`,
`force_process=True`, recorded deterministic backend) followed by aggregation
without re-acquisition — acquisition AND drafts regenerated, top-level
`force_process=True`, all 7 targets with `acquisition_cache_hit=False` and
`process_cache_hit=False`, real network events 19:06:50–19:07:07 UTC
2026-09-08. The intermediate unknown=7 reports were the documented
conservative cache-reuse policy working as designed, superseded by this
genuine live acquisition; nothing was relabelled. Population: 7 targets /
37 page instances / 30 unique URLs; all 30 selected pages verified
hash-UNCHANGED against the dated September 8 full-site archives (recorded,
never assumed). Final evidence: report
`evaluation-af3c4e803ae9dc8b5be6` (evidence untouched), figure registry
`5b99abfb…`, publication manifest `0a1d6495…`, and the final reviewed PDF
`f3b3e1d8…` (3,629,479 B, SHA-256-verified). The Figure 6 known note
is resolved in render #6: subtitle and caption now use conditional wording
("Cached drafts, when present…").

## 3. Claim rollup

Per `data/claims.yaml` (12 claims) and the post-freeze receipts:

| Claim | Disposition and boundary |
| --- | --- |
| Static source compilation, source boundary, provenance chain, live-case-study configuration, Codex portability, figure auditability, human-review gate, manuscript bindings, agent surfaces, adoption attribution | Supported, each bound to named artifact paths and/or citations; all resolve |
| SkillWeaver distinction | Supported as a source-tier claim against three citations |
| Provider choice causes measurable quality difference | Pending: human ratings remain at zero rows (`rating_status: pending`, `agreement: pending_two_rater_workflow`); credentialed OpenAI and installed-model Ollama runs were not attempted (2 opt-in skips by design) |

Intervals remain model-reference quantities on dependent small samples; the
7/7 observations are `live` evidence for the configured targets only. Hashes
establish byte consistency, not signer identity or scientific truth.

## 4. Remaining risks

- **r2b and r10 are CONFIRMED-by-construction classifications**, not live
  defects: both probes execute retired probe-side code shapes. Their
  authoritative replacements are on record (`r2c` REFUTED;
  `test_command_backend_unsafe_description_fails_run`,
  `test_validate_generated_body_rejects_unsafe_provider_description`).
- **Serve rate limiting is a deliberate, documented non-feature** on the
  loopback discovery surface; the render-side bounded-read remainder (H4) is
  now implemented and tested.
- **Polish-wave items resolved**: bibliography accents, title braces, the
  Attebury year, F-A1 PNG binding, and the Fig 5/Fig 6/footnote cosmetics
  are fixed and verified in the v2 gates (see section 2); they are no longer
  open risks.
- **DOI/publication posture**: version DOI `10.5281/zenodo.22663907` is
  reserved on production Zenodo draft 22663907 (unsubmitted, zero files) and
  registers only on publication; the concept DOI was absent from the observed
  draft response and must be read from the actual published response once
  one exists — no identifiers are derived. The title page displays the
  authentic reserved DOI; the config and release receipts record its
  reserved and unpublished status, and the rendered text makes no
  publication assertion. The remote corrective metadata
  PUT **succeeded** — authenticated receipt
  (2026-09-08T17:42:54Z; `upload_type: software`, MIT, reserved DOI stable,
  reservation guards held, `files_after: []`). **File uploads remain
  paused** under the current release-state hold pending the final independent
  archive PASS and explicit root advance; public GitHub remains private with
  no push or tag. Local evidence is complete without waiting for those
  remote steps.
- **Pre-existing cosmetic/compatibility notes** (unchanged, no infrastructure
  altered to silence them): parent numeric scanner false-positive on the
  inverse-CDF exponent `-1`; source-relative figure paths in authored docs;
  custom `manuscript_bindings` config key; MathJax font-component metadata
  warning; untagged PDF (visual/keyboard checks do not establish full PDF
  accessibility compliance).
- **The public-template clean-index audit is inapplicable** to this private
  sidecar and was recorded separately; no confidentiality boundary was
  changed.
- The composition `combined_sha` follows the parent compound-digest semantics
  (`manuscript_composition.py:136`); artifact-audit confirmed this is not a
  defect. MCP exposes a documented subset, not a conformance claim.

## 5. Files changed

Per the closed-lane handoffs; the pre-polish frozen tree closed at **80
tracked modifications + 20 untracked entries** (historical count, before
the polish wave). Counted at reconciliation, immediately before archive
freeze, the tree stands at **80 tracked modifications + 23 untracked
entries**: the pre-polish set plus `docs/extending.md`, this document, and
the publisher's `docs/publication.md`.

| Lane | Owned files changed |
| --- | --- |
| methods lane | `research.py`; `tests/test_statistics.py`, `tests/test_scholarship.py`; `docs/statistics.md`, `docs/evaluation.md` (`statistics.py` verified clean, zero changes) |
| integrations lane | `mcp_server.py`, `serve.py`, `install.py`, `runtimes.py`, `packdiff.py`, `signature.py`, `policies.py`; six owned test modules; `docs/mcp.md`, `docs/install-drift.md`, `docs/runtimes.md`, `docs/policies.md`; `skills/skillarum/references/workflows.md` |
| figures lane | `figures.py`; `tests/test_figure_quality.py`; `docs/figures.md` |
| acquisition lane | `site_snapshot.py`, `crawler.py`, `pipeline.py`, `urls.py`, `models.py`, `config.py`, `generators.py`, `render.py`, `redaction.py`, `quarantine.py`, `repo_source.py`; eight owned test modules; `docs/source-refresh.md`, `docs/repo-source.md` |
| manuscript lane | `manuscript.py`, `publication.py`, `cli.py`; `docs/manuscript/` sections, `config.yaml`, `references.bib`; `data/claims.yaml`, `data/citations.yaml`; six owned test modules; binding-contract documentation |
| docs lane | root `README.md`, `AGENTS.md`, `TODO.md`; `docs/README.md`, `docs/AGENTS.md`, `docs/tutorial.md`, `docs/ROADMAP_adoption.md`, `docs/extending.md` (new); `tests/README.md`, `tests/AGENTS.md`; `src/skillarum/AGENTS.md` |

No canonical output, installed skills, or client configuration were written
by any source lane; canonical generation was executed exclusively by
the release lane after the freeze release.

**Polish-wave additions** (render-ready v2): bibliography and citation
metadata (`docs/manuscript/references.bib`, `data/citations.yaml`),
version/date/DOI publication metadata (`docs/manuscript/config.yaml`,
`CITATION.cff`, `.zenodo.json`), figure generator fixes and the F-A1
registry binding (`src/skillarum/figures.py` and the figure registry), and
publisher documentation (`docs/publication.md`, new), and the provenance
repair (`src/skillarum/render.py`, `src/skillarum/pipeline.py`,
`tests/test_source_reference_integrity.py` (new), `tests/test_scholarship.py`;
15 new tests across four verified runtime hashes). This document plus the
README author-metadata reconciliation are the docs lane contribution and land
before frozen source-archive construction; provisional source capture
`b2f321` is superseded by the final capture that follows this addendum.

## 6. Verification

All commands ran in a shared locked venv.
**The authoritative current receipts are the post-fix suite (555 passed,
2 skipped, 92.14% coverage — +15 provenance controls and the snapshot
regression) and the final live-evidence identity below; every earlier
figure — 437/439 passed, 91.69% coverage, the pre-polish 537/92.17% row,
the v2 540/92.16% row, 20 PDF pages, the d32d6f74, dce8812d, and 8663c3bd PDFs,
registries 1dc1c2cd, 6f83d09d, and 7804bc90, reports evaluation-2a63bf9c
and evaluation-8e9d9d3f, 11 figures/22 files, 61 bindings, 77 artifacts — is
historical and superseded.**

| Gate | Command | Observed result | Exit |
| --- | --- | --- | --- |
| 1 | `pytest tests/ --cov=src --cov-fail-under=90` | **555 passed, 2 skipped (opt-in providers), 92.14% coverage** (floor 90; +15 provenance controls and snapshot regression over the superseded v2 540/92.16% row) | 0 |
| 2 | `ruff check src tests` | All checks passed | 0 |
| 3 | `ruff format --check src tests`; `compileall src tests scripts` | 75 files already formatted; compile clean | 0 |
| 4 | `skillarum validate` (canonical) | 7/7 packages ok after regeneration (strict validation proves the serialization fix; the pre-regeneration FAIL was the expected old-serialization state) | 0 |
| 5 | `research build --output-dir output --json` | rc 0 (canonical build on the regenerated live packages; report `evaluation-af3c4e80`; promotion record above covers the by-design F20 first failure) | 0 |
| 6 | Security reconciliation battery `repro.py r1..r10` | **15/15 probe verdicts match expectations, zero unexpected** (RETEST-MAP rev 6; standing record from the frozen-source run) | 0 |
| 7 | Parent stage 03 render | exit 0 through render #6 (science PASS); final Letter PDF 1.7 `f3b3e1d8…` (3,629,479 B, DOI title page) + HTML suite | 0 |
| 8 | `research publication --require-rendered` + `research validate` | Manifest ok, schema v1; **29 bibliography == 29 citations, 12 claims, 12 figures**, 0 errors; final manifest `0a1d6495…` | 0 |

Independent checks on the pre-polish frozen run: the independent artifact audit (read-only) verified the frozen
manifest 85/85 files hash-OK, all 12 render-ready identity hashes match disk,
80/80 publication artifacts, 22 declared figure hashes + 2 sidecars bound to
report `e50c1d58…`, gate receipts match artifacts, 8/8 installs re-verified
with the exact `_tree_hash` recipe, operator skill 9 functional files
byte-identical, and re-ran the F20 loader (AII complete=True 899/899; Math
complete=False 890/1228 with 338 persistent). MCP smoke: 9/9 (release) and
independently **12/12** against the exact registered command
(`python -m skillarum mcp --root <repo>`, repo venv, write disabled),
including pre-init `-32000`, root escape `-32602`, write gate, and explicit
truncation. Install/drift: **8/8 exit 0** (clean). Science full QA: **PASS**
— 20 PDF pages inspected at 110 DPI with zero unresolved tokens, CP
endpoints matching independent oracles, HTML desktop/mobile/keyboard checks
clean with zero console errors, 11 images loaded, and the no-fabrication
sweep confirmed zero rating rows and pending agreement.

**Render-ready v2 re-verification.** After the polish wave, both independent
reviewers re-verdicted the fresh render (Phase A double PASS) against the v2
identity: PDF `d32d6f74…` (21 pages), figure registry `1dc1c2cd…`, HTML
index `53edf9d1…`, evaluation summary `e2a862a9…`, publication manifest
`73b4bac3…`, research-build receipt `faf52b34…`, manuscript composition
`6a4ee718…`, verification receipt `cd49817f…`. The review copy
byte-matches
the rendered PDF (SHA-256 verified; first-choice filename unused, no
overwrites). This v2 identity is historical, superseded by the final
live-evidence identity below.

**Final live-evidence identity (authoritative).** Phase A closed on render
#6: PDF `f3b3e1d8176bd0c148dd66f19202f321e0046e5bd89aa9953d9188fd370251fa`
(3,629,479 B, the review deliverable, SHA-256-verified), figure
registry `5b99abfbb8e0d3ba…`, publication manifest `0a1d6495c4a05d4b…`,
evaluation report `evaluation-af3c4e803ae9dc8b5be6` (evidence untouched) — 7/7 observations `source=live` (real network
events 19:06:50–19:07:07 UTC 2026-09-08, `acquisition_cache_hit=False` and
`process_cache_hit=False` on every target, `force_process=True` at top
level), population 7 targets / 37 page instances / 30 unique URLs, and all
30 selected pages hash-unchanged against the September 8 archives (recorded,
never assumed). Science approval and the SHA-256 verification cover exactly
these bytes; the Figure 6 subtitle and caption now carry conditional
wording ("Cached drafts, when present…"), resolving the accept-with-note
minor. Tests are unchanged at 555 passed / 2 skipped / 92.14%
(caption-only delta: targeted 55 passed, no full-suite rerun). The
post-`force_process` slice re-verified the final canonical
packages: 8 installs and 8 drift checks clean, MCP smoke 9/9 on current
data.

## 7. Follow-ups

1. **Upload the final checked assets** to production Zenodo draft 22663907
   and verify filenames, sizes, and SHA-256s (publisher; the corrective
   metadata PUT succeeded per its receipt, but file uploads await the final
   packaging output receipt; the draft stays unsubmitted and the reserved
   DOI unchanged).
2. **After the user's PDF review**: publish the Zenodo record; read the
   registered version-DOI status and any concept DOI from the actual
   published response rather than deriving identifiers, then push the local
   commit, tag `v0.2.0`, and create the GitHub release with prepared notes
   (remote currently has 0 releases/0 tags; local HEAD `dae17ec` is ahead of
   remote `main` `8f95311` and preserved by design; public visibility
   unchanged).
3. **Source-overlap embed** in the manuscript after fixture coordination
   through Codex (the fixture registry must carry `metadata.source_urls`
   before the embed can pass validation).
4. **Real two-rater human ratings and credentialed provider runs** remain
   external prerequisites; nothing local can establish them.

Pending after this document: the release lane performs the final source capture
on these exact doc bytes (provisional capture `b2f321` is superseded),
regenerates the publication inventory per the final-write rule, reruns gate
8 with the final docs in the input fingerprint, runs parent stage04 LAST,
and performs the exact frozen-snapshot comparison. Asset uploads stay
paused under the current release-state hold until the independent archive
PASS and explicit root advance. No source document embeds the archive's
own hash, so no self-referential hash cycle exists.
