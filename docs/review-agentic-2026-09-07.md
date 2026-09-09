# Skillarum agentic and manuscript revision — 2026-09-07

This follow-up supersedes the implementation and verification counts in the
[initial review](review-2026-09-07.md). Dates use America/Los_Angeles; the live
retrieval receipts use UTC on 2026-09-08. The requested template path resolves
to this self-versioned Skillarum checkout in the private sidecar. Existing dirty
work was preserved; this revision was not committed, pushed, or published.

## 1. Surface map

| Surface | Owning source | Delivered evidence |
| --- | --- | --- |
| Statistical methods | `src/skillarum/statistics.py`, `research.py` | Explicit policy, independently checked intervals and agreement, reconstructable report summaries |
| Figures | `src/skillarum/figures.py` | Eleven registered figures, SVG/PNG companions, interval point data, source hashes |
| Manuscript bindings | `src/skillarum/manuscript.py`, `docs/manuscript/` | Sixty-one source-derived bindings, rendered-file hashes, source and token inventories |
| Build orchestration | `src/skillarum/publication.py`, `scripts/z_generate_manuscript_variables.py` | Nine-step build receipt, writer lock, input-change detection, failure receipts |
| Agent access | `src/skillarum/mcp_server.py`, `docs/mcp.md` | Six stdio MCP tools, resources and review prompt; real registered-command verification |
| Operator skill | `skills/skillarum/` | Portable operator instructions installed in Codex, separate from generated website packages |
| Current source corpus | `site_snapshot.py`, declared profiles | Two validated HTML archives, seven refreshed and installed reference skills |
| Scholarship | `data/claims.yaml`, `data/citations.yaml`, manuscript bibliography | Eleven bounded claims, twenty-seven bibliography entries, twenty-five cited keys |
| Verification | Real-file, local-HTTP and subprocess tests; parent renderer | Source suite, independent read-only review, PDF and browser checks |

Four requested Herdr OMP tabs divided methods, integrations, figures, and an
independent read-only manuscript/build review. The primary builder integrated
and corrected the implementation handoffs, reproduced failures, and performed
release verification. The independent reviewer closed its three findings after
rechecking the corrected code. No agent handoff was treated as test evidence.

## 2. Issues found and fixed

The statistical layer now owns a validated policy for confidence levels,
bootstrap eligibility and seeds, and rubric bounds. Exact binomial intervals
reject fractional or Boolean counts. Bootstrap input validation precedes the
small-sample return, and ordinal ratings have distributions and modal summaries.
Kappa remains undefined when its denominator is zero. Report loading verifies
the stored hash and reconstructs statistics from raw observations and ratings;
a rehashed but inconsistent current-format summary is rejected. Legacy reports
are explicitly upgraded rather than silently treated as current-format evidence.

The manuscript now derives observed quantities, configured parameters,
statistical-policy values, provenance identifiers, tables, captions, and alt text
from their owning data. A binding receipt records each value's source family,
source hashes, tokens used per section, and rendered hashes. Independent
reconstruction catches stale inputs and forged receipts even when a forger
recomputes a self-hash. Unknown or malformed tokens and literal run numerals
fail validation. Mathematical constants, identifiers, bibliographic metadata,
and explicit author/title/date declarations remain authored content; the
numeric guard is a syntax check, not a semantic proof that all prose is true.

The formal model defines its notation and external-environment assumptions,
uses five numbered propositions with separate justifications, and cross-references
seven equations. The evaluation states its completed-observation unit,
row-specific denominators, missingness, and selection/dependence limitations.
The introduction, methodology, case studies, related work and reproducibility
sections distinguish implemented contracts, observed results and unmeasured
human usefulness. Citations and claims are validated against their ledgers.

Figure generation binds the persisted report to the actual in-memory content,
preserves text in accessible SVGs, checks required PNG companions, and uses
direct labels and explicit missing-data semantics. The new proportion figure
shows exact intervals and eligible denominators. Its data sidecar has a version,
figure identifier and report hashes; malformed or inconsistent sidecars fail.
All captions and alt text are injected from the registry into the manuscript.
The publication allowlist now includes both binding receipts and figure point data.

The publication build serializes writers, writes a pending receipt before work,
checks the input snapshot again before declaring success, and records exception
failures with completed steps. Hydration validates all sections before writing,
uses atomic individual-file replacement, prunes stale generated companions, and
rejects overlapping source/output locations. A reproduced malformed archive
summary now produces a failed build receipt rather than leaving stale success.

MCP validates JSON-RPC envelopes and tool arguments, confines paths and symlinks
to the configured root, verifies discovery cards against packages, and reports
read truncation explicitly. Oversized resources fail rather than silently truncate.
Tool failures and protocol errors use their respective response channels;
notifications receive no response. The fixed evaluation-summary tool uses the
verified report loader. Write access is disabled in the installed configuration.
The authored operator skill explains source boundaries, verification, regeneration,
and the separate MCP interface without relying on checkout-relative installation links.

Subprocess coverage now records the real CLI and MCP executions. The locked
pytest-cov/coverage configuration uses coverage's subprocess patch, as documented
by [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html)
and [coverage.py](https://coverage.readthedocs.io/en/latest/config.html#run-patch).
The aggregate coverage floor remains 90%; no new source was excluded to pass it.
A test that accidentally shared the rendered figure registry now uses its own
real temporary registry, removing interference with concurrent rendering.

## 3. Claim rollup

| Claim | Disposition and boundary |
| --- | --- |
| Run-dependent manuscript content is injected | Verified: 61 binding entries, 24 inventoried source inputs and 11 hydrated Markdown files; reconstruction and adversarial receipt tests pass |
| Figures agree with their report | Verified: 11 registry entries, 22 SVG/PNG files byte-identical on a second generation from the same final report; interval point data also identical |
| Skills reflect the dated live refresh | Verified for seven configured targets; all seven installed package drift checks are clean |
| Institute HTML inventory is complete | Verified within its declared sitemap scope: 899 of 899 accepted HTML URLs |
| Math4Wisdom is fully downloaded | Not claimed: 890 accepted HTML pages from 1,228 discovered URLs; strict completeness remains false for 338 attachment URLs |
| MCP and operator skill are available | Verified: enabled root-bound stdio registration, six tools, nine resources, review prompt; authored skill installed with matching file hashes |
| Statistical intervals imply population performance | Not supported: the small selected targets and pages are dependent; intervals are model-reference quantities |
| Human quality or independent-rater agreement is established | Not supported: zero supplied ratings; status remains pending |
| Formal propositions are machine-checked proofs | Not claimed: stated implementation properties with explicit assumptions and written justifications |
| PDF/HTML and local software are verified | Source suite and visual checks pass; the final parent gate receipt is authoritative for the frozen output snapshot |

The live refresh used new crawler state and replaced the active lookup/install
state. The prior generated output was retained outside active lookup as a
recovery backup. Math4Wisdom's unresolved set comprises 309 non-HTML responses,
28 over-limit attachment responses, and one missing video. No discovered wiki
page remains unresolved. This is an HTML archive, not a media backup or a claim
about private, unlinked, query-specific, or JavaScript-rendered pages. See
[source refresh](source-refresh.md) and the archive summaries for exact boundaries.

## 4. Remaining risks

Human usefulness and rater independence still require actual collected reviews.
Two external-provider integration tests remain opt-in and were skipped; no
new OpenAI or local-model performance result is asserted. MCP exposes the
documented subset and has not been certified against every optional protocol
feature. The server does not enforce a complete initialized-session state machine.
Its registered command becomes available to newly initialized Codex sessions.

The numeric-prose guard does not detect every possible semantic restatement of
a number. Hashes detect inconsistency, not scientific truth or signer identity.
The build lock does not make the whole output tree transactional, and individual
atomic writes do not guarantee recovery from every operating-system failure.
Byte-identical figures from the same stored report do not imply byte-identical
PDFs across changing toolchains or metadata timestamps.

The HTML's equations depend on the configured MathJax delivery. Browser QA
recorded no console errors and one font-component version-metadata warning;
the equations rendered and fit the viewport. The PDF is untagged, so the visual
and keyboard checks do not establish full PDF accessibility compliance.
The manuscript has no assigned DOI. No external publication occurred.

## 5. Files changed

The main new modules are `manuscript.py` and `statistics.py`; the new publication
and site-archive modules from the first review remain part of this revision.
Changes span the CLI, research layer, figure generator, MCP server, manuscript
sections and bibliography, claims/citation ledgers, tests, dependency lock,
operator skill and its directory guidance. The earlier refresh/security fixes
to installation, ingestion, runtime projection and serving are preserved.

The operating guides are [manuscript bindings](manuscript-bindings.md),
[statistics](statistics.md), [figures](figures.md), [MCP](mcp.md),
[source refresh](source-refresh.md), and the [release checklist](release-checklist.md).
Generated output and installed local configuration are not staged source changes.
The existing dirty baseline was not reset or folded into an unrelated commit.

## 6. Verification

| Check | Observed result |
| --- | --- |
| Frozen source suite, Python 3.12 and locked dependencies | 437 passed, 2 opt-in skips; exit 0 |
| Coverage including real subprocesses | 91.69% aggregate; 93.57% statements and 86.33% branches |
| Locked Ruff 0.15.21 lint and format | Passed; 77 source/test files already formatted |
| Whitespace and project signposts | `git diff --check` and the sidecar signpost checker passed |
| Research build | Nine steps passed, including bibliography, archives, figures and binding reconstruction |
| Publication and research validation | 77 allowlisted artifacts verified with rendered outputs required; research validation passed |
| Parent stage 03 render | Exit 0; 20-page PDF and HTML with 11 research figures |
| Final PDF inspection | All 20 final raster pages identical to inspected pages; formalism, tables and figures inspected at page scale; no unresolved tokens |
| Final PDF metadata | Correct title and author, Letter, PDF 1.7; no encryption, forms or embedded JavaScript |
| Final figure repeat | All 22 SVG/PNG files byte-identical; point data identical |
| HTML desktop and mobile | 1,440 px and 390 px viewport checks, no page overflow, all 11 images loaded, seven display equations fit, no broken internal anchors |
| HTML keyboard | Tab exposes skip link; Enter focuses `main-content` |
| Registered MCP process | Tool/resource/prompt calls pass; write and root-escape controls reject; final report hash matches disk |
| Installed skills | Seven website package drift checks clean; all three operator-skill functional files match source |
| Negative controls | Rehashed report/receipt forgery, source mismatch, malformed point data, unsafe output overlap, build input drift, symlink escape and invalid protocol inputs rejected |

The detailed local evidence is in `output/reports/agentic-review-verification.json`,
with supporting receipts and screenshots in `output/reports/agentic-review/`.
`output/reports/publication-manifest.json` is the publication artifact inventory.
The parent stage 04 validator ran after all output evidence and manifest writing
and exited zero with all nine checks passed. Its receipt is
`output/reports/rendered_provenance.json`; the validation summary is
`output/reports/validation_report.json`. Noncritical notes remain for authored
source-relative image paths, the custom manuscript-binding configuration key,
and the inverse-CDF exponent `-1` being scanned as an unsupported observation.
Rendered image paths and the actual mathematical expression were inspected.

A subsequent read-only public-release provenance audit returned
`CLEAN_INDEX_INCOMPLETE: project root is outside the release repository`.
It reported no source, configuration, stage or output fingerprint drift. That
audit requires placement in the public template release index; this private
sidecar project deliberately remains outside it. No confidentiality boundary was
changed to satisfy the public-release check. Post-freeze project research and
publication validation still passed; no generated output was edited afterward.

## 7. Follow-ups

The implemented local scope is complete after the frozen-output gate passes.
Separate evidence-collection work can add real human ratings and provider runs;
media archiving would require an explicitly broader acquisition policy.
Reserve a DOI and decide publication scope only when releasing the manuscript.
Use the release checklist for future regeneration, and always rerun the final
parent gate after changing rendered output. There are no pending implementation
items delegated to the Herdr agents from this pass.
