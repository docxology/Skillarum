# Skillarum Architecture

This document describes the system's internal architecture, module boundaries, and trust relationships after recent modularization improvements.

## Pipeline Overview

`WebsiteCrawler` acquires normalized `PageRecord` values. `prepare_corpus()` turns a `BundleRecord` into bounded `PreparedCorpus` input. A `SkillGenerator` returns a `SkillDraft`, and `render_skill()` writes a portable `SKILL.md` plus its provenance manifest.

```text
YAML profile
    ↓
SourceProfile → TargetSpec → WebsiteCrawler → BundleRecord
                                      ↓
                              PreparedCorpus
                                      ↓
             Deterministic / OpenAI / Ollama / Command / Fallback
                                      ↓
                                SkillDraft
                                      ↓
                           SKILL.md + manifest.json
```

Each run records stage outputs under a stable `output/runs/<profile>-<fingerprint>/01_acquire` through `05_render` identity. `state.json` records `planned → acquiring → preparing → generating → validating → rendered`, or `failed` with a diagnostic manifest. Acquired bundles are reusable through configuration-aware `output/.cache/bundles/`; prepared generator drafts are reusable through `output/.cache/drafts/`. Cache envelopes include pipeline/cache versions, profile/target/corpus/generator fingerprints, provider configuration, and payload checksums, so malformed, stale, or altered state is discarded. `--refresh` invalidates acquisition only, while `--force-process` explicitly reruns the selected generator. Per-target locks prevent duplicate concurrent work. The rendered skill directory is indexed in `output/skills/index.json` only after package validation.

## Module Map and Responsibilities

The following modules handle distinct aspects of the pipeline:

### `redaction.py`
**Responsibility**: Secret redaction for rendered skill artifacts. Two-pass defense: pattern scrub to replace credential-shaped tokens in text before writing, then a non-leakage gate asserting no secret-shaped token survives in any output payload. Biases toward over-redaction on purpose—false positives turn tokens into parameter placeholders, while false negatives leak credentials.

**Trust boundary**: Input text from generators and source pages is untrusted; output text must be safe for public distribution.

### `policies.py`  
**Responsibility**: Declarative policy packs over rendered skill content. The `security` pack applies severity-ranked regex rules over the rendered output as a safety check on untrusted LLM/source-derived instruction text. `error` severity fails validation, `warning` reports but passes.

**Trust boundary**: Generated `SKILL.md` content is untrusted input; policy validation is a release gate protecting consumers of the rendered skills.

### `install.py`
**Responsibility**: Install rendered skills into agent harness roots with drift tracking. Creates a sidecar install manifest recording canonical hashes, enabling `drift` to re-hash both canonical and installed copies and report stable issue codes without mutating anything (read-only repair-plan pattern).

**Trust boundary**: The canonical skill package must be validated before installation; installed copies are under user control and may drift from canonical state.

### `evals.py`
**Responsibility**: Fixture evaluation with release-blocking numeric gates. Hostile fixture pages run through the pipeline, then releases gate on measurable invariants: secret non-leakage, effect-tag correctness, and frontmatter validity. Results are recorded as dated baselines with evidence origin `fixture`.

**Trust boundary**: Fixture pages are controlled test inputs; the evaluation gates must catch any pipeline regression that would compromise output safety or correctness.

### `runtimes.py`
**Responsibility**: Cross-runtime frontmatter compilation targets. Per-target field allowlists and length limits allow one rendered skill to compile to `claude`, `codex`, and `agentskills` runtime dialects without invalid fields. Unknown fields are dropped with notes rather than passed through.

**Trust boundary**: Source frontmatter may contain fields incompatible with target runtimes; compilation ensures the output is valid for the specific target harness.

### `serve.py`
**Responsibility**: Read-only HTTP discovery surface over rendered skills. Provides GET routes for `/healthz`, `/skills`, `/skills/{area}/{name}`, and `/index.json` to enable agent discovery and browsing. Deliberately excludes invoke semantics (documented in `v1-boundary.md`).

**Trust boundary**: Serves only validated, rendered skill packages; no dynamic execution of skill content occurs.

### `quarantine.py`
**Responsibility**: Quarantine-then-promote for refreshed skill drafts. When a refreshed draft differs from the cached canonical draft, it is quarantined for that run only and becomes canonical only after a second clean regeneration confirms it. Prevents flaky or failed LLM refreshes from silently replacing good skills.

**Trust boundary**: Cached drafts are assumed-good state; refreshed drafts are suspect until proven stable across multiple generations.

### `mcp_server.py`
**Responsibility**: Zero-dependency MCP stdio server over Skillarum's CLI functions. Thin JSON-RPC 2.0 stdio loop delegating to the same functions the CLI uses, with JSON Schema tool definitions, structured errors, and protocol-clean stdout (tracebacks to stderr).

**Trust boundary**: MCP clients are external callers; the server confines package paths to an explicit root. Discovery and validation are read-only; rebuilding an index writes local state and requires write-enabled server configuration. It never invokes source-page instructions or a provider.

### `index_profile.py`
**Responsibility**: Derive a profile from a site's own index page. `parse_index` is pure: it keeps same-origin links under a path prefix in document order, skips query-string actions and fragments, and labels each link with the nearest preceding bold or heading text. `build_index_profile` turns the entries into one exact-page target each, with unique ids, an authored description, and budgets that cover every target once; the `derived_from` block records index URL, retrieval time, SHA-256, entry count, and sections.

**Trust boundary**: The index page is untrusted HTML fetched only through `WebsiteCrawler.fetch_raw`, so robots, origin, SSRF, and request-budget rules apply. Link text and section labels become description text and are stripped of angle brackets; they never become instructions.

### `repo_source.py`
**Responsibility**: Repository-as-source ingestion (second source type alongside website acquisition). Detects ecosystem markers (README, pyproject.toml, package.json, Makefile), extracts README commands, and fingerprints selected content alongside clean commits or dirty working-tree identity for provenance. Cloning and network access remain out of scope—callers provide an already-checked-out repo path.

**Trust boundary**: Local git repositories are trusted input (under caller control); extracted content is treated as source material subject to the same validation as web-scraped content.

## Configuration

Profiles define a base origin, source area, extraction selector, network limits, and named targets. A target can list exact URLs, constrain paths with boundary-aware prefixes or include/exclude shell-style patterns, and opt into link discovery through the profile's `follow_links` setting. Initial examples intentionally use exact URLs so a profile cannot accidentally expand into an entire site. A large collection is enumerated from the site's own index with `profile-from-index`, which still yields exact URLs. Two opt-in extraction keys, `preserve_blocks` and `title_separator`, refine text and titles; left unset they are omitted from the profile fingerprint, so existing caches stay valid. A target's optional `description` is authoritative for the rendered frontmatter.

Profiles also declare `generation` defaults: backend, model, Ollama endpoint and model, context budget, prompt budget, and retry policy. Omitted CLI options keep these values; supplied CLI options take precedence. Secrets are never profile values and are never persisted.

## Generator Contract

All generators implement:

```python
generate(corpus: PreparedCorpus) -> SkillDraft
```

The command backend receives `PreparedCorpus.to_payload()` as JSON on stdin and must return a JSON object with non-empty `name`, `description`, and `body`. This makes local models, hosted APIs, and other agent runtimes replaceable without changing crawling or rendering. `OllamaGenerator` sends a non-streaming `/api/chat` request with a JSON schema, explicit context options, and a bounded untrusted prompt, then validates `message.content` before the parse stage. Prompt truncation is explicit and recorded in draft metadata rather than being left to silent server-side context truncation. `GenerationConfig`, `GenerationAttempt`, and `GenerationTrace` make provider behavior inspectable without changing the public generator method. Every attempt records backend, model, timing, retry count, status, cache key, and a sanitized error. `FallbackGenerator` composes a primary and secondary backend; the built-in opt-in `auto` chain is OpenAI (when configured) → Ollama → deterministic. Default generation is deterministic. Provider retries are bounded to two attempts by default and only cover transport/timeouts and 408/429/5xx; malformed JSON, invalid schema, unsafe output, and section validation failures are terminal for that provider and may trigger fallback. Generated bodies should separate semantic knowledge from procedural guidance and verification; the renderer adds the authoritative provenance and limitation section for every backend. The persisted trace also records the ordered fallback chain, so a successful deterministic result after an Ollama failure remains distinguishable from a deterministic result selected directly. Provider drafts additionally reject executable code fences and common destructive or exfiltration instructions; deterministic extraction may preserve hostile source wording as quoted, untrusted reference data.

## Trust Boundaries

Page content is source data, not instructions. The OpenAI prompt places it in an explicit untrusted corpus delimiter and requests source-grounded Markdown only. Redirects are constrained to the configured origin, obvious private/local hosts are rejected, and external command arguments are passed with `subprocess.run(..., shell=False)`. `Fetcher` is the acquisition boundary; `HTTPFetcher` is the only v1 implementation. It streams bounded responses, counts robots/redirect/retry requests, rate-limits all attempts, and records request/rejection events with an explicit `request_attempt` flag. Research telemetry uses that flag and the persisted request count rather than raw event length; public hostname resolution is checked before a connection so DNS aliases cannot bypass private-address safeguards. Rendered manifests retain requested, final, canonical, retrieval-time, status, and content-hash fields for every page, as well as generator metadata, cache identity, trace, truncation warnings, and explicit limitations. The discovery index revalidates each `SKILL.md` and checks its manifest hash before advertising the artifact.

Canonical example output is partitioned by source area. The area is declarative profile metadata and is part of the package manifest, discovery index, cache identity, and research observation; it is not inferred from scraped prose.

```text
output/skills/
├── Math4Wisdom/
│   ├── Three-Minds/SKILL.md
│   ├── Three-Minds-Exposition/SKILL.md
│   └── Minds-Research/SKILL.md
└── Active-Inference-Institute/
    ├── Institute-Overview/SKILL.md
    ├── Institute-Foundations/SKILL.md
    ├── Institute-Programs/SKILL.md
    └── Institute-Projects/SKILL.md
```

## Artifact Integrity

New packages use manifest schema `2` and `SKILL.md/v2`. Validators remain backward-readable for schema-1 packages, but new output always emits the new fields: run ID, cache identity, generation trace, request events, generator fingerprint, artifact hash, source page hashes, and limitations. Package publication uses a staging directory and two atomic directory renames with a recoverable backup and a brief absence window; the discovery index is itself atomically written after validating every package.

## Research and Publication Layer

The scholarly layer consumes completed run and skill manifests; it does not reach into crawler internals or reinterpret source-page prose. The flow is:

```text
run manifests + skill manifests
        ↓
typed EvaluationObservation records
        ↓
descriptive statistics + evidence ledger validation
        ↓
evaluation report + figure registry + manuscript tokens
        ↓
parent-template publication renderer
```

`CitationRecord`, `ClaimRecord`, `EvaluationCase`, `EvaluationObservation`, `EvaluationReport`, and `ReviewRating` are typed contracts in `skillarum.research`. A supported claim must point to a citation, observation, or artifact. Pending and hypothesis claims remain visible but cannot be presented as measured results.

Research observation construction has two integrity layers. The package validator checks that a snapshot is internally well-formed and hash-valid; the observation reader then compares its profile, target, area, source URL order, retrieval fields, raw-content hashes, prepared-text hashes, truncation flags, and warnings with the persisted prepared corpus for the same run. A mismatch downgrades provenance completeness even when the package itself remains structurally valid. Schema-1 packages remain readable but report an unavailable lineage check rather than being silently upgraded.

Counts, rates, ranges, medians, and missingness are labeled with sample sizes. Exact Clopper–Pearson intervals are used for proportions; seeded bootstrap intervals are emitted only for samples with at least twenty continuous observations. The initial live matrix is reported as case-study evidence. Human agreement is computed only for overlapping rows from two distinct raters.

Figures are canonical SVG artifacts with deterministic PNG companions when the research extra is installed. The registry and its integrity manifest contain source and artifact hashes, captions, alt text, sample size, uncertainty method, limitations, and manuscript references. The manuscript binds named placeholders to reports, executable statistical settings, source profiles, and registry captions. Reconstruction checks compare the resulting text and binding receipt with those inputs. BibTeX keys are cross-checked against both the citation ledger and manuscript citation commands.
### Publication dependency order

`statistics.py` owns the numerical policy, `research.py` owns evidence records
and ledgers, `manuscript.py` owns text binding, and `publication.py` orders their
operations. The builder locks the output, snapshots its inputs, validates the
ledgers, constructs the report and figures, checks archive receipts, hydrates
text, and reconstructs the expected binding. A source change during the build
fails its receipt. Parent-template rendering and final validation follow after
all source writers have finished.
