# Repository-as-source ingestion

A second source type alongside website acquisition
(`src/skillarum/repo_source.py`): a local git repository can seed a prepared
corpus. Cloning and network access stay out of scope — callers pass an
already-checked-out repo path.

## Entry-point detection

`extract_entrypoints(repo_path)` detects ecosystem markers:

| Marker key | File |
| --- | --- |
| `readme` | `README.md`, `readme.md`, or `README.rst` (first hit) |
| `pyproject` | `pyproject.toml` |
| `package_json` | `package.json` |
| `makefile` | `Makefile` |

Only present markers appear in the returned mapping.

## README command extraction

`extract_readme_commands(repo_path)` pulls shell commands mentioned in the
README (`$ cmd` prefixed lines and fenced `sh`/`bash`/`shell` blocks), in
order, deduplicated. These become setup/usage hints for agents.

## Corpus text

`repo_context_text(repo_path)` assembles prepared-corpus-style text for the
generator: a `<repository_entrypoints>` JSON section, a `<readme_commands>`
section when commands exist, then one `<repo_file path="…">` section per
collected file, including README narrative. Per-file text is bounded by `max_chars_per_file` (default 20,000).

## Collection limits

File iteration is deliberately bounded:

- Skip list: `.git`, `.venv`, `node_modules`, `__pycache__`, `.ruff_cache`,
  `.mypy_cache`
- Text suffixes only: `.md`, `.txt`, `.py`, `.ts`, `.js`, `.toml`, `.json`,
  `.yaml`, `.yml`
- At most 500 files, each at most 500,000 bytes; symlinks skipped

## Commit-SHA fingerprints

`repo_fingerprint(repo_path)` provides provenance identity that replaces the
URL fingerprint used for web sources:

- Clean Git checkout: commit SHA plus `content_sha256` for the selected files.
- Dirty Git checkout: `git_worktree` identity combines the commit and selected
  working-tree byte hash, with `commit_sha` retained separately.
- Otherwise a SHA-256 tree hash over the collected text files (same limits)
  → `{"type": "tree", "sha": …}`

The tree fallback applies consistently when `git rev-parse` cannot read HEAD
and when `git status` cannot run (for example a corrupt index or dubious
ownership): the worktree state is unknown, so neither a clean-commit nor a
dirty-worktree claim would be honest. The `type` field always names which
identity a caller received.

A commit SHA alone does not describe uncommitted source content; the working
tree digest closes that gap for the bounded selected file set. The tree-hash
fallback keeps the fingerprint defined for non-git directories.
