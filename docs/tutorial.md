# Skillarum Tutorial

A complete walkthrough from repository clone to your first rendered skill installed in a harness.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) Python package manager
- Git
- Python 3.10+
- An agent harness (Claude, Codex, or agents-compatible) or just an output directory

## 1. Clone and Setup

```bash
git clone https://github.com/docxology/Skillarum.git
cd Skillarum
uv sync
```

## 2. Health Check with `doctor`

Before running any extraction, verify your environment with `doctor`.
`doctor` creates `output/` and `output/.cache` even with `--no-network`
(`--no-network` only skips the live Ollama `/api/tags` request):

```bash
uv run python -m skillarum doctor --profile data/sources/math4wisdom.yaml --output-dir output --no-network --json
```

This outputs the health status:

```json
{
  "checks": [
    {
      "name": "profile",
      "ok": true,
      "path": "data/sources/math4wisdom.yaml"
    },
    {
      "name": "output_writeability",
      "ok": true,
      "path": "output"
    },
    {
      "name": ".cache_writeability",
      "ok": true,
      "path": "output/.cache"
    },
    {
      "name": "ollama_endpoint",
      "ok": true,
      "skipped": true
    },
    {
      "configured": false,
      "name": "openai_configuration",
      "ok": true,
      "secret_persisted": false
    }
  ],
  "ok": true
}
```

## 3. Run Against the Bundled Math4Wisdom Profile

Extract skills from the configured Math4Wisdom pages using the deterministic backend:

```bash
uv run python -m skillarum run --profile data/sources/math4wisdom.yaml --backend deterministic --output-dir output
```

This produces three skills:

```
output/skills/Math4Wisdom/Three-Minds/SKILL.md
output/skills/Math4Wisdom/Three-Minds-Exposition/SKILL.md
output/skills/Math4Wisdom/Minds-Research/SKILL.md
```

## 4. Pack a Skill

Package a rendered skill as a zip for distribution:

```bash
uv run python -m skillarum pack output/skills/Math4Wisdom/Three-Minds/SKILL.md
```

This validates the package structure and writes `<skill>.zip` next to the
package (`--zip` overrides the path). The archive's `packer` label is
self-asserted; `--packer <label>` sets it and `--verify-signature` checks a
detached `skillarum.sig` signature stored inside the archive:

```
packed: output/skills/Math4Wisdom/Three-Minds/SKILL.zip
sha256: f0ca2c721697567a649f02e557566bef13e768b302bb017470116bee475ff64c
```

The hash above is illustrative output, not a receipt; your hash differs.

## 5. Verify with Security Policy

Run the security policy pack over the rendered skill:

```bash
uv run python -m skillarum verify --policy security output/skills/Math4Wisdom/Three-Minds/SKILL.md
```

Output when clean:

```
verify: ok
ok package_validation
ok generation_body
ok policy
```

Exit code 0 means verification passed.

## 6. Install into a Harness

Install the validated skill into Claude's skills directory:

```bash
uv run python -m skillarum install output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness claude
```

This creates `~/.claude/skills/Three-Minds/` and returns:

```json
{
  "canonical_path": "output/skills/Math4Wisdom/Three-Minds/SKILL.md",
  "harness": "claude",
  "installed_path": "/Users/yourname/.claude/skills/Three-Minds/SKILL.md",
  "installed_tree_hash": "190d1cf12202b9a3efb09f12bb99a3ccd9fa9abef1b2d30039868a7dd68c121d",
  "ok": true,
  "schema": "skillarum.install-manifest",
  "skill_md_hash": "5c89cf3607d53cff35c912b433b4aa82962c49b79370082c34b1c475a9b40167",
  "source_tree_hash": "190d1cf12202b9a3efb09f12bb99a3ccd9fa9abef1b2d30039868a7dd68c121d",
  "version": 1
}
```

## 7. Drift Detection

Check for drift between the canonical skill and the installed copy:

```bash
uv run python -m skillarum drift output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness claude
```

When no drift exists:

```
drift: ok
```

JSON format shows the full drift status:

```bash
uv run python -m skillarum drift output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness claude --json
```

```json
{
  "canonical_tree_hash": "190d1cf12202b9a3efb09f12bb99a3ccd9fa9abef1b2d30039868a7dd68c121d",
  "harness": "claude",
  "issues": [],
  "ok": true,
  "recorded": {
    "canonical_path": "output/skills/Math4Wisdom/Three-Minds/SKILL.md",
    "harness": "claude",
    "installed_path": "/Users/yourname/.claude/skills/Three-Minds/SKILL.md",
    "installed_tree_hash": "190d1cf12202b9a3efb09f12bb99a3ccd9fa9abef1b2d30039868a7dd68c121d",
    "schema": "skillarum.install-manifest",
    "skill_md_hash": "5c89cf3607d53cff35c912b433b4aa82962c49b79370082c34b1c475a9b40167",
    "source_tree_hash": "190d1cf12202b9a3efb09f12bb99a3ccd9fa9abef1b2d30039868a7dd68c121d",
    "version": 1
  },
  "skill": "output/skills/Math4Wisdom/Three-Minds/SKILL.md"
}
```

## 8. Examine the Manifest

Each rendered skill includes a manifest with provenance metadata:

```bash
cat output/skills/Math4Wisdom/Three-Minds/manifest.json | head -20
```

Shows schema version, area, effect tags, source URLs, generator info, and integrity hashes.

## 9. Read References and Sources

Agent-usable source provenance lives in `references/sources.json`:

```bash
cat output/skills/Math4Wisdom/Three-Minds/references/sources.json
```

```json
{
  "profile_id": "math4wisdom",
  "schema": "skillarum.sources/v1",
  "sources": [
    {
      "content_sha256": "755d9575bacc16e4290b6f5834f570146dd4f3531808287ed9eb04c404288d2b",
      "fetched_at": "2026-08-31T04:37:07.813426+00:00",
      "final_url": "https://www.math4wisdom.com/wiki/Exposition/StoryOfThreeMinds",
      "requested_url": "https://www.math4wisdom.com/wiki/Exposition/StoryOfThreeMinds",
      "status_code": 200,
      "title": "Math 4 Wisdom. \"Mathematics for Wisdom\" by Andrius Kulikauskas. | Exposition / StoryOfThreeMinds",
      "truncated": false,
      "url": "https://www.math4wisdom.com/wiki/Exposition/StoryOfThreeMinds"
    }
  ],
  "target_id": "three-minds"
}
```

## 10. Read Regeneration Configuration

The `regeneration.json` file contains the configuration needed to reproduce this skill:

```bash
cat output/skills/Math4Wisdom/Three-Minds/regeneration.json
```

```json
{
  "backend": "deterministic",
  "generator_fingerprint": "1ce347e5672c513c4e7add66385ddd4f4a50e5a52346c50ac133e2544d8dcbd1",
  "manifest_schema_version": 2,
  "profile_fingerprint": "d2eb2a4fc1fbda3285633c1fa1ee60235a60fabc14a0bc87ff013e2727e206d2",
  "profile_id": "math4wisdom",
  "requested_skill_name": "Three-Minds",
  "run_id": "math4wisdom--797d145a40b4d210bb24",
  "schema": "skillarum.regeneration/v1",
  "skill_format": "SKILL.md/v2",
  "source_urls": [
    "https://www.math4wisdom.com/wiki/Exposition/StoryOfThreeMinds"
  ],
  "target_id": "three-minds"
}
```

This enables third-party reproduction of the same skill with the same profile and backend.

## Next Steps

- Explore other commands: `validate`, `index`, `serve`, `cache inspect`
- Try the `mcp` server mode for agent integration
- Examine the evaluation and research tooling with `evaluate`, `figures`, `research`
- Run with different backends: `--backend ollama` or `--backend openai`

## Troubleshooting

- If `doctor` reports issues, check output directory permissions and profile validity
- If `install` fails with encoding errors, ensure your system locale supports UTF-8
- If `verify` fails with policy violations, examine the rendered content for security issues
- Use `--json` flags for machine-readable output suitable for debugging