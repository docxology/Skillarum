# Install and drift detection

Install rendered skill packages into agent harness roots with drift tracking
(`src/skillarum/install.py`), a read-only repair-plan pattern: `drift` never
mutates anything, it only reports.

## Harness roots

Known harness skills roots (relative to the user's home directory, or to
`--home`):

| Harness | Skills root |
| --- | --- |
| `codex` | `~/.codex/skills` |
| `claude` | `~/.claude/skills` |
| `agents` | `~/.agents/skills` |

```bash
uv run python -m skillarum install output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex
uv run python -m skillarum drift output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
```

Both commands accept `--home <dir>` to redirect the root (tests and
multi-user setups) and `--json` for machine-readable reports.

## Install workflow

1. The target `SKILL.md`'s package is validated (`validate_skill_package`);
   installation refuses structurally invalid packages.
2. Under an install lock, the full package and sidecar receipt are staged and
   validated before replacing the destination through recoverable renames.
3. Binary assets participate in byte hashes. Self-installation and symlink
   destinations are rejected; the existing installation survives a failed copy.

The sidecar (`schema: skillarum.install-manifest`, `version: 1`) records:

- `harness`, `installed_path`, `canonical_path`
- `skill_md_hash` — SHA-256 of the installed `SKILL.md`
- `source_tree_hash` — stable hash over the canonical package tree (sorted
  relative paths + per-file content hashes)
- `installed_tree_hash` — the same hash over the installed copy

The tree hash covers whole file trees, not just `SKILL.md`, so auxiliary
files in a package participate in drift detection too.

## Drift report

`skillarum drift` re-hashes both the canonical package and the installed copy
and compares them against the recorded sidecar. It reports `ok: true` when
everything matches, otherwise a list of issues with stable codes:

| Issue code | Meaning | Action |
| --- | --- | --- |
| `install_manifest_missing` | No `.skillarum-install.json` at the destination | `resync` (re-run `install`) |
| `install_manifest_invalid` | Sidecar is unreadable JSON or missing required fields | `resync` (re-run `install`) |
| `installed_skill_missing` | Installed `SKILL.md` absent | `resync` |
| `installed_skill_drift` | Installed `SKILL.md` hash differs from install-time hash | `resync` |
| `installed_package_drift` | Any installed companion file changed | `resync` |
| `installed_package_symlink` | Installed package tree contains a symlink | `resync` after removing the symlink |
| `canonical_skill_drift` | Canonical package tree changed since install | `resync` |
| `canonical_package_symlink` | Canonical package tree contains a symlink | remove the symlink, re-run `install` |

Human output prints `drift: ok` or `drift: drifted` followed by one
`code: message -> action` line per issue. The command exits `0` when the
report is clean and `1` when any issue is present, so it can gate scripts.
Because `drift` is read-only, "repair" always means an explicit re-install.

Installation destinations use the validated portable frontmatter name. A
frontmatter `name` that is not a single portable directory name (for example
`../../../Outside`) is rejected before anything is created, so the destination
always stays inside the harness skills root. This replaces an existing
slug-named harness skill and removes obsolete companion files through package
replacement. Canonical build output keeps the requested human-facing directory
name; it is not renamed by installation.
