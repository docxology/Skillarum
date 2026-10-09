# Skillarum backlog

Reviewed 2026-10-09. This project is a self-versioned checkout with its own
`docxology/Skillarum` remote. Work from its root; generated output stays local.
See [the current review record](docs/review-2026-09-07.md) — implementation
and verification counts superseded by
[the agentic revision](docs/review-agentic-2026-09-07.md) — and
[release checklist](docs/release-checklist.md) for current verification.

## Current evidence and follow-ups

- [x] Add an ordered offline research build with failed-gate receipts.
- [x] Reproduce and correct report, manuscript, figure, installation, discovery,
  repository identity, and checksum validation defects.
- [x] Preserve unknown acquisition labels, exclude unavailable telemetry from
  its denominator, and keep ordinal ratings outside the continuous bootstrap.
- [x] Qualify formal properties, security boundaries, case-study claims, and
  statistical interpretation in the manuscript and claim ledger.
- [x] Collect and retain the dated live acquisition matrix and source archives;
  regenerate and reinstall both source areas from the September refresh.
- [ ] Collect real ratings from two independent people with source evidence,
  then adjudicate disagreements. Distinct IDs cannot establish independence.
- [ ] Exercise credentialed OpenAI and installed-model Ollama integration when
  those external services are available; default skips are intentional.
- [x] Reserve and publish a version DOI (0.2.0: 10.5281/zenodo.22663907;
  concept DOI 10.5281/zenodo.22663906). Nothing in a local hash inventory
  authenticates a signer or establishes scientific truth.
- [x] Derive one skill per Math 4 Wisdom Research page from the wiki's own
  index (`profile-from-index`, 528 targets).
- [x] Author and version the `math4wisdom-cube` investigation skill and run
  three independent investigators over it (2026-10-09).
- [ ] Rerun the cube investigation from `blind-brief.md` with investigators
  from more model vendors and at least one human, recording the model that
  actually ran. Acceptance: a new dated directory under `docs/investigations/`.
- [ ] Recompute anvil-c's holonomy claim (X-6) in the cube checker, or mark
  it refuted. Acceptance: an `M` item with a passing check, or a superseding
  note.
- [ ] Ask the Math 4 Wisdom author the discriminating questions E2, E5, E7,
  E8 and record answers as new `S` entries.
- [ ] Add a per-area catalog skill for the 528 Research skills so an agent
  can route by index section without loading all descriptions.

## Historical work

The following entries describe earlier implementation work, not current gate
receipts or proof that all defects have been eliminated. In particular, historical
per-module coverage and security language must not be treated as current facts.

### Completed / Closed

- **Robots.txt 3xx redirects followed (bounded)** `(implemented)`.
  `RobotsCache.allowed()` (src/skillarum/crawler.py) follows up to 5 3xx
  hops, re-validating each target DNS/public under the profile allow-private
  policy, and fails closed on missing Location, invalid/unsafe target, unbounded
  chain, or other non-2xx/non-404 status. Tests in tests/test_more_edges.py and
  fixtures in tests/conftest.py (redirect, limit, missing-Location,
  invalid-target, unsafe-target).

- **Declared live-matrix plan wired into `evaluate`** `(implemented)`.
  Added `research.load_cases()` and `evaluate --cases` (default
  data/evaluation/cases.yaml) so observations are attributed to declared case
  ids instead of drifting from run-manifest keys. research.py, cli.py,
  data/README.md.

- **Provider options forwarded through `evaluate --profile`** `(implemented)`.
  Added --model/--fallback-backend/--generator-command/--ollama-* to
  `evaluate` and forwarded them to run_profile_from_path (cli.py), so
  provider-driven evaluations are reproducible from the CLI.

- **`LICENSE` added matching the declared MIT license** `(implemented)`.
  Standard MIT file (copyright Daniel Ari Friedman, Active Inference
  Institute) matching docs/manuscript/config.yaml and CITATION.cff.

- **`CommandGenerator` sanitizes external stderr in the raised error**
  `(implemented)`. Non-zero-exit diagnostics pass through `_sanitize_error`
  (generators.py) at construction.

- **Content-hash docstring corrected** `(implemented)`. `sha256_bytes` now
  documents that the streaming fetcher hashes the decoded body (stable across
  transfer encodings).

- **Module-level coverage lifted to >=90% everywhere** `(implemented)`.
  Added no-mock tests: crawler robots edge cases, render manifest
  schema/identity/trace rejections, render existing-manifest-unreadable and
  symlink, frontmatter malformed, utils atomic-write failure cleanup, and
  research ledger/publication/adjudication validator error paths.
  Final: render.py 95.2%, utils.py 94.1%, crawler.py 91.9%, research.py
  92.0%, aggregate 92.34% (from 90.61% at start of round 3).

- **`ruff format` adopted and gated** `(implemented)`.
  Ran `ruff format` repo-wide (23 files, semantics-preserving) so
  `ruff format --check` is clean (29 files). Added `ruff format --check` to
  the documented gates in AGENTS.md and docs/release-checklist.md.

- **`doctor` side-effect documentation** `(implemented)`. `doctor --help`
  now states it creates output/cache directories and issues a live Ollama
  /api/tags request unless --no-network is given; --no-network help updated.
