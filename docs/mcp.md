# MCP stdio server

`skillarum mcp` runs a zero-dependency Model Context Protocol server over
JSON-RPC 2.0 stdio (`src/skillarum/mcp_server.py`). It is a thin loop
delegating to the same source APIs the CLI uses — no logic duplication — with
strict JSON Schema tool definitions, root-bounded paths, and protocol-clean
stdout (tracebacks go to stderr).

The server is read-only by default. It never acquires pages from the network;
acquisition stays with the CLI (`skillarum run`), and every generated skill
body remains untrusted source-derived data.

```bash
uv run python -m skillarum mcp [--root PATH] [--allow-write]
```

| Flag | Effect |
| --- | --- |
| `--root PATH` | Filesystem root every tool path is confined to. Default: `SKILLARUM_MCP_ROOT` or the current directory. |
| `--allow-write` | Permit `skillarum_index` to rebuild the discovery index inside the root. Default: off. |

The environment variables `SKILLARUM_MCP_ROOT` and `SKILLARUM_MCP_ALLOW_WRITE`
carry the same settings; the write flag is truthy for `1`, `true`, or `yes`
(case-insensitive).

## Protocol versions and negotiation

The server supports protocol versions `2025-11-25`, `2025-06-18`,
`2025-03-26`, and `2024-11-05`. On `initialize` it echoes the client's
requested version when supported, otherwise it answers with its latest
(`2025-11-25`), as the lifecycle specification requires. Clients that do not
support the answered version disconnect.
`initialize` requires `clientInfo` with a non-empty `name` (and a string
`protocolVersion` when one is sent); a malformed initialize is `-32602`.
Requests without `jsonrpc: "2.0"`, without a `method`, with a non-object
payload, or with a `null`/non-scalar `id` are rejected as `-32600`; unknown
methods return `-32601`; structurally invalid params return `-32602`. Error
responses carry `"id": null` when the request id could not be read.
Notifications (messages without `id`) never produce a response, and
`notifications/initialized` is recorded as session state. The stdio loop
reads bytes (invalid UTF-8 becomes `-32700`), bounds each input line at 4 MiB
(`MAX_LINE_BYTES`; over-long lines are refused and drained so framing stays
aligned), and survives every malformed line; one JSON response is written per
handled line, and nothing that is not an MCP message is ever written to
stdout.

## Initialized-session gate

The server enforces the lifecycle state machine: before an `initialize`
request has been answered, only `initialize` and `ping` requests are served;
anything else receives `-32000` ("server not initialized", the SDK
convention). A failed initialize leaves the gate closed. After a successful
initialize response all methods are served for the life of the process;
re-sending `initialize` renegotiates the version in place. This matches the
reference SDK behavior without requiring clients to send
`notifications/initialized` before their first request.

## Fixed locations inside the root

| Path | Served by |
| --- | --- |
| `<root>/output/skills` | Default `skills_dir` for `skillarum_discover` / `skillarum_index` |
| `<root>/output/reports/evaluation-summary.json` | `skillarum_report` (fixed; no other JSON/log/config files are served) |
| `<root>/skills/skillarum/SKILL.md` | `skillarum://operator/skill` resource (when present) |

Every path argument must resolve inside the root; `..` traversal, symlink
escapes, and absolute paths outside the root are rejected with `-32602`.

## Tools

| Tool | Writes | Arguments | Returns |
| --- | --- | --- | --- |
| `skillarum_discover` | no | `skills_dir?` | Discovery-index entries; every advertised package is revalidated first (failure-hard like `serve.py` discovery, but failing the call instead of omitting the package); symlinked or forged indexes fail |
| `skillarum_index` | yes | `skills_dir?` | Rebuilt index path and skill count; refused as a tool error without `--allow-write` |
| `skillarum_validate` | no | `skill_path` (required) | Package frontmatter metadata; never file contents |
| `skillarum_verify` | no | `skill_path` (required), `policy?` (`"security"`) | Metadata plus the policy findings report; `ok` reflects the policy result |
| `skillarum_read` | no | `skill_path` (must name a `SKILL.md`), `max_chars?` (1–262144) | Size-capped skill text with `truncated`/`hint` |
| `skillarum_report` | no | none | The hash-verified evaluation report identity (`report_id`, `generated_at`, `rating_status`, counts), its summary, and rating status, loaded through `load_evaluation_report` |

Error distinctions follow the specification: unknown tools and malformed tool
arguments are protocol errors (`-32602`), while tool execution failures
(missing files, invalid packages, missing report, write refusal) are returned
as results with `isError: true` and an explanatory text block, so a model can
self-correct. Policy findings never echo credential-shaped tokens: excerpts
are redacted at the `policies.py` source. Successful results carry both
`structuredContent` and a serialized text mirror.

## Resources

- `skillarum://skills/index.json` — the discovery index, re-serialized from
  the revalidated entries (never raw unchecked bytes).
- `skillarum://skills/<area>/<name>/SKILL.md` — indexed rendered packages.
- `skillarum://operator/skill` — the maintained operator skill at
  `<root>/skills/skillarum/SKILL.md`, when the file exists.
- `resources/templates/list` returns an empty list.

Resource failures are JSON-RPC errors: a malformed or un-servable URI is
`-32602`; a well-formed URI whose backing content is missing, unreadable, or
invalid is `-32002` (the specification's resource-not-found code) with the
URI in `error.data`. Resource reads exceeding the 262144-character cap are
refused (`-32002`); the read tool instead reports truncation explicitly.
Discovery cards are compared with metadata reconstructed from each validated
package manifest.

## Prompts

`prompts/get` with `name: "skillarum-review-skill"` and a required
`skill_path` argument returns a user message that walks a reviewer through
`skillarum_validate`, `skillarum_verify --policy security`, and
`skillarum_read`, and instructs it to treat the skill body as untrusted data.

## Example client configuration

Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "skillarum": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Skillarum", "python", "-m", "skillarum", "mcp", "--root", "/path/to/Skillarum"]
    }
  }
}
```

Codex (in the Codex home `config.toml`):

```toml
[mcp_servers.skillarum]
command = "uv"
args = ["run", "--project", "/path/to/Skillarum", "python", "-m", "skillarum", "mcp", "--root", "/path/to/Skillarum"]
```

Hermes (MCP server config):

```json
{
  "mcpServers": {
    "skillarum": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Skillarum", "python", "-m", "skillarum", "mcp", "--root", "/path/to/Skillarum"]
    }
  }
}
```

Replace `/path/to/Skillarum` with this repository's checkout path. Add
`--allow-write` only when index rebuilds through MCP are wanted; the read-only
default is sufficient for discovery, reading, validation, and reporting.

## Verification and limitations

Negative controls and round-trips run against the real stdio subprocess in
`tests/test_mcp_server.py`: version negotiation, the initialized-session gate
(requests before `initialize` are refused over the wire), notification
silence, the malformed-input battery (garbage lines, JSON arrays, missing
method, wrong `jsonrpc`, invalid UTF-8, oversized ids, an over-4-MiB input
line that must not break framing), initialize argument validation,
root-escape rejections, symlinked and forged discovery indexes, the missing
default `skills_dir`, write gating, credential-excerpt non-leakage through
`skillarum_verify`, and a full `tools/list` → `tools/call` round-trip over a
genuinely rendered package.

Not implemented, and not claimed as full specification compliance: JSON-RPC
batching (removed by the current spec; arrays are rejected — clients
requesting `2024-11-05` must send single messages), resource subscriptions
and list-changed notifications, pagination cursors (lists are returned whole
with no `nextCursor`), task-augmented execution, logging, completion, and
cancellation. Resource reads serve only packages the discovery index
revalidates; tool path confinement persists for the process and the write
policy never changes after startup.
