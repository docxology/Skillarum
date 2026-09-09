# Skillarum Improvement Roadmap (competitive-synthesis pass 2026-08-30)

Consolidated from 4 parallel reviews of: xiaokillua/skillpress, xiaokillua/skillforge,
tripleyak/SkillForge (879 stars), attebury/skillpress (npm), elisymlabs/husk,
gericke98/skillwright (npm), cslsolow/SkillForge, sulthonzh/skillforge.
Full per-source findings: delegation summaries 2026-08-30 (deleg_edda50db).

**Status 2026-09-08.** Every item in waves 1–3 ships today: `redaction.py`,
effect tags under `metadata.skillarum_effect`, `references/sources.json`,
`regeneration.json`, `evals.py`, `install`/`drift`, `policies.py`,
`verify`, `repo_source.py`, `runtimes.py`, `serve`, `mcp_server.py`, and
`quarantine.py`. Two surfaces remain library-level without a CLI entry point:
repository-source ingestion (no `run --repo` flag; `repo_source.py` is a
library API by design, without cloning) and `compile_frontmatter` (defined in
`runtimes.py`, not yet called by the renderer). The waves below are the
design rationale; see [`extending.md`](extending.md) for the current recipes.

## Wave 1 - Safety & provenance closes (small, high priority)

1. **Secret redaction + non-leakage gate** (from skillwright)
   - Port token/prefix/Luhn/sensitive-key classifier to render.py: two-pass scrub of
     SKILL.md bodies + manifests before write; over-redaction bias; final gate asserts
     no secret-shaped token in any output file (skills, index.json, manifests).
   - Effort: ~1 day. Closes real hole: hostile public pages with embedded tokens.

2. **Effect tags on rendered skills** (from skillwright)
   - `metadata.skillarum_effect: readonly|mutating|destructive` frontmatter field; deterministic floor from
     URL/method classifier over PreparedCorpus (POST/DELETE forms, auth, payment verbs);
     LLM backends may raise but never lower severity; enforced in render validation.
   - Effort: 1-2 days. Pure additive metadata + validator.

3. **`references/sources.json` in rendered packs** (from xiaokillua/skillpress)
   - Ship per-source {url, title, kind, fetched_at} with the rendered skill so consuming
     agents (not just operators) can trace claims. Feed from acquire/parse source registry.
   - Effort: small. Provenance becomes agent-usable, not operator-only.

4. **Regeneration manifest inside pack** (from skillpress direction, better realized)
   - Emit skillarum manifest (profile URL, stage versions, run id, backend) alongside
     SKILL.md for third-party reproduction.
   - Effort: small. Natural extension of stable-identity design.

5. **Inspect-gated export with `--json`** (from skillpress pack/inspect)
   - Any bundle export hard-gates on structural validation report; exit codes 0/1/2.
   - Effort: small. Turns export into a trust boundary.

## Wave 2 - Verification & drift (medium, high priority)

6. **Per-skill `evals/` regression fixtures** (from tripleyak)
   - Hostile-corpus fixtures (embedded token page, destructive-action page) run through
     LLM backends; release gates: secret non-leakage, safety-tag correctness, frontmatter
     validity; dated evidence-origin-tagged baseline (fixture vs live per AGENTS.md).
   - Effort: 2-3 days. Converts provenance evaluation into numeric release gates.

7. **Install manifest + drift doctor** (from attebury/skillpress)
   - `skillarum install --harness <name>` writes sidecar install manifest
     (skill_md_hash, source_tree_hash); `doctor --installed` re-hashes canonical vs
     installed, reports stable drift codes; read-only repair-plan (codes -> actions).
   - Effort: 2-3 days combined. Closes the only currently unverified boundary.

8. **Security policy pack** (from attebury skill-lint)
   - `validate --policy security`: reject rendered instructions containing `curl | sh`,
     `sudo`, hardcoded secrets, absolute home paths. Declarative regex rules,
     profile-wirable; severity error/warning.
   - Effort: ~2 days. Hardens untrusted LLM-output surface.

9. **`verify` command** (from skillwright verify)
   - Round-trip rendered SKILL.md through generation validators independently of a run.
   - Effort: ~0.5 day.

## Wave 3 - Reach & distribution (medium, medium priority)

10. **Repo-as-source ingestion** (from xiaokillua/skillforge)
    - Second source type: shallow-clone + entrypoint detection + README command
      extraction, commit-SHA fingerprints, into acquire/prepare.
    - Effort: medium. Broadens from websites-only.

11. **Cross-runtime frontmatter compile** (from tripleyak)
    - Per-target field allowlists (claude/codex/agentskills), 64/1024 char limits,
      migration notes; render-stage targets.
    - Effort: small-medium. Composes with existing portable-name split.

12. **Read-only `serve` + index-card schema** (from husk)
    - Extend index.json entries (name, description, path, skill_md_hash, area,
      source_urls); stdlib HTTP server: GET /skills, /skills/{area}/{name},
      /index.json, /healthz. Invoke explicitly out of scope (v1-boundary note).
    - Effort: ~1.5 days.

13. **MCP server mode** (from skillpress mcp_server.py)
    - Hand-rolled JSON-RPC stdio over existing CLI functions: initialize negotiation,
      tools/list with JSON Schema, structured errors, clean stdout.
    - Effort: medium. Only once CLI surface stabilizes (post Wave 2).

14. **Quarantine-then-promote for refreshed drafts** (from skillwright)
    - Divergent refreshed draft -> quarantined slot in run manifest; promote after
      second clean confirmation.
    - Effort: ~2 days. Prevents flaky LLM refresh from poisoning good skills.

## Deliberately not adopted
- skillpress HTML extraction (inferior to Skillarum parse stage)
- skillpress fixed SKILL.md template (Skillarum content strictly richer)
- LLM-as-judge scoring harness (provenance evaluation covers core need)
- Self-distillation loop (cslsolow) - different domain; leakage-filter principle only
- husk execution surface (Skillarum never executes generated code)
- Command contracts (attebury) - prose skills, not tool-scoped repos
- RED/GREEN baseline gate, friction mining, hook advisor (tripleyak) - need live
  agent harness; revisit at v1.0
