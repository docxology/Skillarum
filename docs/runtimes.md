# Cross-runtime compilation

Per-runtime frontmatter compilation targets (`src/skillarum/runtimes.py`) so
one rendered skill compiles to the `claude`, `codex`, and `agentskills`
runtime dialects without invalid fields.

## Targets

| Target | Allowed fields | Name max | Description max |
| --- | --- | --- | --- |
| `agentskills` | `name`, `description`, `license`, `allowed-tools`, `metadata` | 64 | 1024 |
| `claude` | `name`, `description`, `license`, `allowed-tools`, `metadata` | 64 | 1024 |
| `codex` | `name`, `description`, `license`, `allowed-tools`, `metadata` | 64 | 1024 |

These are conservative project projections, not complete runtime specifications.
Unknown fields are dropped with notes. Effect annotations belong under
`metadata.skillarum_effect`; `effect` is not a portable top-level field.
Projection alone does not validate name syntax or guarantee runtime acceptance.
Limits count characters, not bytes, matching the documented runtime limits.
All three targets currently share one allowlist and one limit pair; the
per-target mapping exists so future divergence never changes callers.
See the [Agent Skills specification](https://agentskills.io/specification).

## `compile_frontmatter`

```python
from skillarum.runtimes import compile_frontmatter

compiled, notes = compile_frontmatter(
    {"name": "three-minds", "description": "...", "metadata": {"skillarum_effect": "readonly"}}, "claude"
)
```

Returns `(compiled_frontmatter, migration_notes)`. The transform is never
silent:

- Fields outside the target allowlist are dropped and recorded as
  `dropped field '<key>' (not supported by <target>)`.
- String fields over the target's length limit are truncated to the limit and
  recorded as `truncated field '<key>' from <n> to <limit> chars for <target>`.

An unknown target raises `ValueError`. Migration notes belong in the caller's
logs or manifests — they are the audit trail for anything the compilation
changed.
