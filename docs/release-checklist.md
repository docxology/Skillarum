# Skillarum release checklist

This checklist is the final gate for a reproducible Skillarum release. It
keeps implementation artifacts, generated skills, and scholarly interpretation
auditable as separate surfaces.

## Invariants

- [ ] The checkout resolves to the intended `docxology/Skillarum` remote,
  with no unrelated worktree changes.
- [ ] `Math4Wisdom/` and `Active-Inference-Institute/` are separate declared
  areas; requested target names, portable slugs, and package paths agree.
- [ ] The default backend is deterministic and offline; `auto` is explicitly
  selected when provider fallback is desired.
- [ ] No credentials, authorization headers, raw private cache, run logs, or
  generated provider responses are staged for publication.
- [ ] Only `output/skills/` is tracked under `output/`; index-derived profiles
  are regenerated with `profile-from-index`, not hand-edited.
- [ ] Authored investigation skills carry a version, a changelog entry for
  every claim change, and a passing checker.

## Ordered local verification

Run from the project root. Every command must exit zero before continuing:

```bash
uv sync --extra dev --extra research
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
uv run --extra dev ruff check src tests
uv run --extra dev ruff format --check src tests
uv run python -m compileall -q src tests scripts
uv run python -m skillarum validate --json output/skills/*/*/SKILL.md skills/*/SKILL.md
python3 skills/math4wisdom-cube/scripts/verify_combinatorics.py --brief
uv run --extra research python -m skillarum research build --output-dir output --json
```

The build checks ledgers and bibliography, aggregates completed run snapshots,
regenerates SVG/PNG figures, validates figure references, and hydrates Markdown.
It writes `output/reports/research-build.json` and
`output/data/manuscript_variables.json`, and a reconstructable
`output/data/manuscript_bindings.json` receipt. The build serializes concurrent
writers and fails if its source snapshot changes during execution. It does not acquire pages, render
PDF/HTML, install skills, or publish externally. A failed step writes a failed
receipt and raises an error. With no completed observations it fails explicitly.

The thin `scripts/z_generate_manuscript_variables.py` hook repeats this build before parent rendering, preventing stale hydrated inputs. Run the canonical renderer from the sibling template checkout, passing whatever path that workspace uses for this checkout; the value is workspace-owned and is not a constant of this repository. In the workspace recorded on 2026-10-12 the historical `working/Skillarum` path no longer resolved, while the lifecycle link `ongoing/docxology/Skillarum` did — see [`investigations/2026-10-12-synesis/validation.md`](investigations/2026-10-12-synesis/validation.md):

```bash
uv run python scripts/pipeline/stage_03_render.py --project <this-checkout-path>
```

Then return to the project root:

```bash
uv run python -m skillarum research publication --output-dir output --project-root . --require-rendered --json
uv run python -m skillarum research validate --evaluation output/reports/evaluation-summary.json --json
```

- [ ] Inspect the final PDF pages and HTML, including figure labels, references,
  author metadata, and absence of unresolved tokens or operational status prose.
- [ ] Verify the final artifact hashes after rendering; declared PDF/HTML counts
  must agree with the files listed in the manifest.
- [ ] Run `python3 scripts/check_signposts.py <this-checkout-path>` from the
  parent sidecar when that script is present. It is absent from the current
  template and sidecar, so the historical check is unavailable
  ([2026-10-12 record](investigations/2026-10-12-synesis/validation.md)).
- [ ] Run the installed Codex quick validator over both output namespaces.
- [ ] Keep fixture, live, and unknown origins distinct; rate denominators include
  completed snapshots only. Failure diagnostics are not a sampled success-rate denominator.
- [ ] Human independence requires collection discipline. Distinct rater IDs alone
  cannot establish independence; undefined kappa is reported as null.
- [ ] Hash inventories establish byte consistency, not signer identity, scientific
  truth, archival durability, or complete absence of secrets.

After all artifact generation, review screenshots, and receipt writing are
finished, run the final parent validation **last**, from the template checkout:

```bash
uv run python scripts/pipeline/stage_04_validate.py --project <this-checkout-path>
```

Check the process exit code and exact rendered-provenance receipt. Individual
green check messages do not override a final input-drift failure. Any later
write under the rendered output invalidates that frozen-snapshot result.

## Live optional checks

- [ ] Re-run deterministic Math 4 Wisdom and Active Inference Institute
  profiles with an explicit retrieval date and preserve the resulting run
  manifest outside source control if it is not part of the release.
- [ ] Run the real local Ollama test when a model is installed, and separately
  verify unavailable-Ollama fallback to deterministic.
- [ ] Enable OpenAI tests only when credentials are supplied through the
  environment; never put them in profiles, command arguments, or manifests.

## Deferred boundary

Browser-rendered pages, JavaScript execution, scheduling, hosted service APIs,
automatic publication, and generated-code execution remain outside v1. A
future fetcher or service must preserve the same source/untrusted-data and
artifact-integrity contracts before it is added.
