# Authored-skill guidance

Follow [the project guidance](../AGENTS.md).

- `skillarum/` is the authored, portable operator skill. Keep its commands
  aligned with the CLI; do not insert live website claims or depend on
  relative checkout paths that break after installation.
- `math4wisdom-cube/` is a versioned investigation skill. Its rules:
  - Bump `metadata.version` in `SKILL.md` and add a `CHANGELOG.md` entry for
    every change to a claim. Patch versions change wording only.
  - Never edit the content of an existing ledger ID (`S`, `M`, `I`, `E`, `C`);
    supersede it with a marked `[x.y.z: …]` note or a new ID.
  - Every `M` item must be recomputed by `scripts/verify_combinatorics.py`
    (standard library only), and `tests/test_index_profile.py` runs it.
  - Quote sources exactly, with their location, in `references/sources.md`.
  - Investigator reports go verbatim under `docs/investigations/<date>-<topic>/`.

Validate frontmatter and every bundled link in both skills.
