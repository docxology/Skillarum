# Skillarum workflows

Commands below assume `SKILLARUM_ROOT` identifies the intended checkout.
Use `--help` when the installed interface differs. Relative paths are resolved
inside that checkout by `uv --directory`.

## Acquisition and refresh

```bash
uv --directory "$SKILLARUM_ROOT" run python -m skillarum doctor \
  --profile data/sources/math4wisdom.yaml --no-network --json
uv --directory "$SKILLARUM_ROOT" run python -m skillarum evaluate \
  --profile data/sources/math4wisdom.yaml \
  --profile data/sources/active_inference_institute.yaml \
  --backend deterministic --live --refresh --output-dir output --json
```

`--refresh` reacquires pages; unchanged prepared input may reuse a generator
draft. `--force-process` on `run` regenerates a draft for unchanged input and
is not a substitute for acquisition. A purge-and-refresh request needs an
empty active output/cache namespace: preserve the old evidence outside that
namespace, acquire into a new output, validate, then replace the active tree.
Do not claim a refresh while still serving an earlier active package.

To cover every page a site lists on its own index, derive the profile rather
than writing it by hand, then run it:

```bash
uv --directory "$SKILLARUM_ROOT" run python -m skillarum profile-from-index \
  --profile data/sources/math4wisdom.yaml \
  --index-url https://www.math4wisdom.com/wiki/Research/Index \
  --prefix /wiki/Research/ --output data/sources/math4wisdom_research.yaml \
  --profile-id math4wisdom-research --id-prefix research \
  --name-prefix Research- --title-separator " | "
```

`snapshot-site --help` exposes the separate website inventory. It records
raw-response archives and explicit discovery limits. Use `--sitemap` for a
published sitemap and seed-based traversal for reachable public HTML. An
incomplete inventory exits nonzero even when its retained archive is valid.
Unsupported media, unlinked pages, private content, and client-rendered pages
are outside a static HTML completeness claim. See the checkout's
`docs/source-refresh.md` for its maintained inventory procedure.

## Research and publication

```bash
uv --directory "$SKILLARUM_ROOT" run --extra research python -m skillarum research build --json
uv --directory "$SKILLARUM_ROOT" run --extra dev --extra research pytest tests/ --cov=src
```

The build orders ledger validation, report construction, figures, archive
verification, manuscript binding, and reconstruction. Reporting parameters
come from `statistics.DEFAULT_POLICY`; captions come from the figure registry.
Keep body placeholders unresolved in authored Markdown. Read the checkout's
`docs/release-checklist.md` for its sibling-template render and final gate.
The software neither invents human ratings nor reserves a DOI.

After rendering, inspect every final PDF page and the HTML's figure alternatives,
equations, references, responsive layout, and keyboard access. Write review
receipts before the final parent validation, then check its exit code and
rendered snapshot. Local validation is not external publication.

## Generated-package installation

```bash
uv --directory "$SKILLARUM_ROOT" run python -m skillarum install \
  output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
uv --directory "$SKILLARUM_ROOT" run python -m skillarum drift \
  output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
```

The installer stages, validates, and replaces a complete generated package;
its destination uses the portable frontmatter slug and always stays inside
the harness skills root — a frontmatter name that is not a single portable
directory name is refused. It expects a generated provenance manifest and
does not install this authored operator skill.

## MCP

```bash
uv --directory "$SKILLARUM_ROOT" run python -m skillarum mcp --root "$SKILLARUM_ROOT"
```

This starts a stdio server and waits for JSON-RPC messages; it is not an
interactive shell. Keep stdout protocol-clean. The server follows the MCP
lifecycle: clients send `initialize` before other requests, and non-lifecycle
requests before that handshake are refused (`-32000`). Client registration
must pass the checkout directory and an explicit filesystem root. Read-only
operation is the default; add `--allow-write` only for authorized index
rebuilding. Use the checkout's `docs/mcp.md` for exact capabilities and
client examples.
