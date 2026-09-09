# Skillarum v1 boundary

Skillarum v1 is a local, static-HTTP website-to-agent-skill pipeline. It
implements declarative profiles, safe same-origin acquisition, robots handling,
bounded streaming responses, deterministic preparation, deterministic/OpenAI/
Ollama/command generation, fallback traces, source-area partitioned portable
`SKILL.md` rendering, and
filesystem artifacts that can be inspected or resumed.

The following are deliberate deferred boundaries:

- Browser automation, JavaScript execution, WebDriver/Playwright, and pages
  whose useful content exists only after client-side rendering.
- Scheduling, watch mode, background crawling, and automatic publication.
- A hosted service, database, queue, multi-user API, or remote artifact store.
- Agent-specific wrappers or runtime installation for Hermes, Codex, Claude
  Code, or other harnesses. v1 emits one canonical portable `SKILL.md` format.
- Automatic interpretation or execution of source-page instructions or
  generated code.

The `Fetcher` protocol is intentionally the extension point for a later
browser-backed implementation. Adding such a fetcher must preserve the v1
trust boundary: public/same-origin policy, robots policy, request/page limits,
response bounds, rate limits, canonical/redirect tracking, and provenance.

## Scholarly publication boundary

The manuscript, claim ledger, citation ledger, evaluation observations, and
figure registry are a research-facing layer over persisted Skillarum
artifacts. They do not turn scraped text into independent scholarly evidence.
Source pages remain untrusted data, live-site results remain snapshots, and
human-review statistics remain pending until two real independent rating files
are present.

Provider output is a separate trust boundary from scraped source text. The
deterministic extractor can preserve hostile source wording as quoted data;
OpenAI, Ollama, and command-provider drafts must additionally pass the provider
output safety policy before they can become agent-facing skills. External
command diagnostics are redacted before entering traces or cache identities.

The project emits source Markdown and deterministic SVG figures. Final PDF or
HTML rendering is delegated to the sibling template toolchain through project
linking; no renderer engine is copied into this private project.
