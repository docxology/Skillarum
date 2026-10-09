# Extending Skillarum

Recipes for the implemented extension surfaces, each with its owning module
and the minimal contract an extension author must satisfy. Everything here is
grounded in current code (`src/skillarum/`); when a recipe and the code
disagree, read the code and fix this document.

## Recipe index

| Recipe | Owning module | Minimal contract |
| --- | --- | --- |
| New generation backend | `generators.py` (`SkillGenerator` protocol, `generator_for()` factory) | `name: str`, `generate(corpus) -> SkillDraft`, `cache_key() -> str`; optional `model` and `requires_retrieval` attributes |
| New fetcher (v1 boundary) | `crawler.py` (`Fetcher` protocol) | `request_count: int` plus `fetch(url, *, kind="page") -> httpx.Response` returning one bounded, non-redirect-following response; injected via `WebsiteCrawler(fetcher=...)` |
| Profile from an index page | `index_profile.py` (`parse_index`, `build_index_profile`), CLI `profile-from-index` | Index HTML read via `WebsiteCrawler.fetch_raw` or a saved file; output is an ordinary profile with exact URLs and a `derived_from` receipt. Regenerate rather than hand-edit |
| New authored investigation skill | `skills/<name>/` (pattern: `math4wisdom-cube`) | `metadata.version` plus `CHANGELOG.md`; separate source/mathematics/interpretation/test ledgers with stable IDs; a stdlib checker for every mathematical item, run from `tests/`; investigator reports verbatim under `docs/investigations/` |
| New source type | `repo_source.py` (library only) | `repo_fingerprint()`, `repo_context_text()`, `extract_entrypoints()`, `extract_readme_commands()`; callers build the `PreparedCorpus`. No cloning, no network, and no `run --repo` flag yet |
| New policy pack | `policies.py` (`POLICY_PACKS`) | Rule dict with `id`, compiled `pattern`, `message`, `severity` (`error` fails `verify`, `warning` reports); users pass `verify --policy <name>` |
| New MCP tool | `mcp_server.py` (`tool_definitions()`, `_tools_call()`) | JSON Schema definition dict plus a dispatch arm; writes must gate on `context.allow_write` and all paths go through `ServerContext.bounded_path` |
| New runtime target | `runtimes.py` (`RUNTIME_TARGETS`, `compile_frontmatter()`) | Per-target field allowlist and length limits; unknown fields are dropped with a note, truncation is never silent. Library utility — the renderer does not call it yet |
| New figure | `figures.py` (`_registry_record()` inside `generate_figures()`) | Must satisfy `validate_figure_registry()`: file exists, no symlink, relative path, hash matches, caption and alt text present, source report hash-matches |
| New manuscript token | `manuscript.py` (`KNOWN_MANUSCRIPT_TOKENS`, `_binding_origin()`) | Token name plus value in `manuscript_variables` and an origin label; figure captions use the dynamic `FIGURE_<ID>_<CAPTION|ALT>` family minted from the registry |
| New claim evidence tier | `research.py` (`ClaimRecord`) | Add the tier to the validator's tier set; a `supported` claim can never carry a `hypothesis` or `pending` tier and needs at least one resolvable evidence reference |

Two source types exist today. HTTP profiles are the CLI-wired path
(`run --profile`). Repository ingestion is deliberately a library surface:
`repo_source.py` reads an already-checked-out local repo, fingerprints it
against `git rev-parse`, and never clones or touches the network.

## Generation backend contract in detail

`generator_for()` resolves `deterministic`, `openai`, `ollama`, `command`,
and `auto`. The command backend receives
`PreparedCorpus.to_payload()` as JSON on stdin (profile/target identity,
fingerprint, warnings, events, `pages[]`, context) and must emit one JSON
object parseable by `SkillDraft.from_mapping` (`name`, `description`,
`body`); the suggested `name` is recorded as metadata and never redirects the
artifact. `auto` prefers OpenAI when `OPENAI_API_KEY` is set, then Ollama,
then deterministic. An explicit `--fallback-backend` (which must differ from
the primary) builds the same chain; unconstructable primaries fall back
rather than aborting. Retries cover transport errors, timeouts, HTTP
408/429/5xx, and transient Ollama daemon failures; malformed JSON and
validation failures are not retried and go straight to the fallback.
Credentials are environment-only and never enter cache identities or
manifests.

## Change ownership during multi-agent waves

Documentation follows the same ownership discipline as code:

- Write ownership is by exact file set, never by adjacency. If a change needs
  a file another lane owns, send an exact request or proposed patch to its
  owner instead of editing it.
- Every directory documents itself: fix the `README.md`/`AGENTS.md` next to
  the code rather than growing cross-cutting guides.
- Historical review records under `docs/review-*.md` are read-only evidence;
  supersede their counts by pointing at the newer record instead of editing
  them.

## Frozen-output protocol

Canonical `output/`, installed skills, and client configuration are frozen
during multi-agent waves. Targeted verification uses isolated temporary
outputs (per-test `tmp_path`, or an explicit `--output-dir` pointing outside
`output/`). Never declare source changes verified using prior render
receipts: a receipt describes the frozen snapshot it was written for, not the
current tree. The release workflow — full source gates, research build,
parent render, independent QA, installation checks, publication manifest,
research validation, and the final parent stage — is owned by
[`release-checklist.md`](release-checklist.md).

## Local validation versus the public-template clean index

This project lives in the private sidecar. Local validation runs the
commands in [`release-checklist.md`](release-checklist.md) and the sidecar
signpost checker from the parent checkout. The public-template clean-index
audit is a separate surface: it requires placement in the template release
index and reports `CLEAN_INDEX_INCOMPLETE` for a private sidecar checkout
without any fingerprint drift. That result is expected here and is not
something to fix by changing confidentiality boundaries.

## See also

- [`architecture.md`](architecture.md) — module map and trust boundaries
- [`operations.md`](operations.md) — provider policy, cache gates, exit codes
- [`v1-boundary.md`](v1-boundary.md) — deliberate non-goals
- [`policies.md`](policies.md) — the `security` pack and verify exit codes
- [`../tests/AGENTS.md`](../tests/AGENTS.md) — no-mocks test conventions
