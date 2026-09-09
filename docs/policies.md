# Security policy packs

Declarative, severity-ranked regex packs over rendered skill content
(`src/skillarum/policies.py`). A policy pack is a safety check on untrusted
LLM/source-derived instruction text: Skillarum never executes generated
content, so policies inspect the rendered `SKILL.md` text itself.

## Running a policy

`skillarum verify` re-runs structural, provenance, safety, and non-leakage
validation independent of any run, and can additionally apply policy packs
over the rendered content. `--policy` is repeatable:

```bash
uv run python -m skillarum verify output/skills/Math4Wisdom/Three-Minds/SKILL.md --policy security
uv run python -m skillarum verify output/skills/Math4Wisdom/Three-Minds/SKILL.md --policy security --json
```

The pack name must be one of `sorted(POLICY_PACKS)` (currently only
`security`); the CLI rejects anything else at argument-parse time. The same
path is available to MCP clients through the `skillarum_verify` tool with
`{"policy": "security"}` — see [`mcp.md`](mcp.md).

## Severity model

Each rule carries a severity:

| Severity | Meaning | Effect on the report |
| --- | --- | --- |
| `error` | Blocker. Credential-shaped tokens, shell-pipe installs, privilege escalation, recursive force-delete. | Sets `error_count`, fails the pack (`ok: false`) |
| `warning` | Informational. Absolute home paths, credential-like `export`/`set` lines. | Sets `warning_count`, never fails the pack |

A finding records the `rule` id, `severity`, a human `message`, an `excerpt`,
and `match_start`/`match_end` offsets. Excerpts are redacted through the
same secret-scrubbing patterns the renderer uses, and `hardcoded_secret`
findings never echo their match at all — the excerpt is `<{secret}>`, so the
token a rule exists to catch is never re-published into reports or MCP tool
output. Offsets locate the text without reproducing it.

## Exit-code mapping

`verify` runs its structural/provenance checks first, then the policy pass.
The command exits:

- `0` — all validators passed and every requested policy pack passed
  (`error_count == 0`).
- `1` — any validator failed, **or** any policy pack produced at least one
  `error`-severity finding. `warning` findings alone still exit `0`; they are
  printed in the human report and present in the `--json` report's
  `checks[name="policy"]` entry with the full `findings` list.

## The `security` pack rules

| Rule id | Severity | Matches |
| --- | --- | --- |
| `curl_pipe_shell` | error | `curl … \| sh/bash/zsh/fish` |
| `wget_pipe_shell` | error | `wget … \| sh/bash/zsh/fish` |
| `sudo_usage` | error | `sudo`/`doas` before apt, yum, brew, pip, npm, make, systemctl, service, rm, chmod, chown, dd, mkfs, mount |
| `rm_rf` | error | `rm -rf`-style recursive force-delete flag combinations |
| `hardcoded_secret` | error | Credential-shaped tokens: GitHub `ghp_`/`gho_`, OpenAI `sk-`, Slack `xox…`, AWS `AKIA`, JWT `eyJ….` |
| `absolute_home_path` | warning | `/Users/<name>/`, `/home/<name>/`, `/root/` |
| `env_var_credentials` | warning | `export`/`set` of a `*SECRET*`/`*PASSWORD*`/`*TOKEN*`/`*KEY*` variable |

The pack is data (`POLICY_PACKS` in `src/skillarum/policies.py`), so new packs
and rules are additive without touching the CLI. The MCP `skillarum_verify`
tool additionally hard-codes the `"security"` enum in its schema and
argument check, so a second pack must update `src/skillarum/mcp_server.py`
in the same change.
