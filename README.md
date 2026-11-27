# Skillarum

Skillarum turns selected public website pages into portable `SKILL.md`
documents for agent harnesses such as Codex, Claude Code, and Hermes. Treat source pages and generated skill bodies as untrusted data. The [local fixture guide](docs/rendering.md#create-fixture-evidence) reproduces the evidence on loopback without running the generated skills.

<p align="center"><img src="cover/skillarum_cover.png" alt="Skillarum cover: public web pages distilled into portable SKILL.md documents" width="360"></p>

**Agent orientation (read in this order):** [AGENTS.md](AGENTS.md) (layer
contract + testing rules) → [backlog](docs/backlog.md) (backlog with acceptance
lines) → `uv run python -m skillarum doctor --profile
data/sources/math4wisdom.yaml --no-network --json` (one-command health) →
`output/skills/index.json` (discovery index for rendered skills; rebuild with
`uv run python -m skillarum index --skills-dir output/skills`).
The checkout includes a published discovery index. The health check creates
the local cache directory if needed, including with `--no-network`.

It separates the work into five inspectable stages:

```text
acquire → prepare → process → parse → render
```

Acquired page records and prepared corpora are written under `output/runs/`;
configuration-aware page bundles and generator drafts are cached under
`output/.cache/`. Run and artifact identities are stable, so repeating the same
invocation updates the same state instead of creating timestamped duplicates.
The rendered skills directory also contains `index.json` for harness discovery.

## Install

Skillarum requires Python 3.11 or newer. Install from the public repository; a
source checkout also provides the bundled source profiles used below:

```bash
git clone https://github.com/docxology/Skillarum
cd Skillarum
uv sync --locked --extra dev --extra research
```

Optional extras: add `--extra llm` for the OpenAI backend or `--extra
research` for evaluation figures.

## Repository layout

Every directory below carries its own `AGENTS.md` (detailed guide) and
`README.md` (quick reference), except the generated `output/skills/` tree
and the dated investigation records.

| Directory | Contents |
| --- | --- |
| [`src/`](src/README.md) | Packaging root — src-layout |
| [`src/skillarum/`](src/skillarum/README.md) | The whole implementation: the implementation modules, no subpackages |
| [`scripts/`](scripts/README.md) | Thin CLI wrappers and the parent-render hydration hook |
| [`tests/`](tests/README.md) | pytest modules plus `conftest.py`, no mock frameworks |
| [`data/`](data/README.md) | Hand-authored inputs: profiles, ledgers, cover metadata |
| [`data/sources/`](data/sources/README.md) | The two declarative source profiles |
| [`data/evaluation/`](data/evaluation/README.md) | Case plan and human rating files |
| [`docs/`](docs/README.md) | Architecture, operations, policies, tutorial, roadmap |
| [`docs/manuscript/`](docs/manuscript/README.md) | Manuscript sources and bibliography |
| [`docs/investigations/`](docs/investigations/2026-10-09-cube/README.md) | Dated independent-investigator records, reports kept verbatim |
| [`skills/`](skills/README.md) | Authored skills: the `skillarum` operator skill and the `math4wisdom-cube` investigation skill |
| [`cover/`](cover/README.md) | The manuscript cover image |
| `output/skills/` | Generated deterministic skill packages and `index.json`, tracked as reviewable output |
| `output/` (everything else) | Generated and disposable; not tracked |

## Quick start

From a source checkout:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend deterministic
```

This renders `output/skills/Math4Wisdom/Three-Minds/SKILL.md`.

### Every Math 4 Wisdom Research page

`data/sources/math4wisdom_research.yaml` has one target per page listed on
the wiki's [Research index](https://www.math4wisdom.com/wiki/Research/Index):
528 skills named `Research-<Page>`. Each description names the page's index
section, except `Research-Introduction`, which is listed before the first
heading and so has none. The profile is generated, not hand-written:

```bash
uv run python -m skillarum profile-from-index \
  --profile data/sources/math4wisdom.yaml \
  --index-url https://www.math4wisdom.com/wiki/Research/Index \
  --prefix /wiki/Research/ --output data/sources/math4wisdom_research.yaml \
  --profile-id math4wisdom-research --id-prefix research \
  --name-prefix Research- --title-separator " | "
uv run python -m skillarum run \
  --profile data/sources/math4wisdom_research.yaml --backend deterministic
```

The rendered packages are committed under `output/skills/Math4Wisdom/`, so an
agent can install them straight from a clone.

### The cube correspondence: an investigation skill

[`skills/math4wisdom-cube/`](skills/math4wisdom-cube/SKILL.md) is an authored,
versioned skill on the cube, its two tetrahedra, Wondrous Wisdom's three
languages, and the proposed Spin(8) triality reading. It keeps source
statements, mathematics, interpretations, and proposed tests in separate
ledgers, recomputes every mathematical claim with
`python3 skills/math4wisdom-cube/scripts/verify_combinatorics.py`, and
includes a protocol for independent investigators. Version 0.1.0 was audited
by three investigators on 2026-10-09; their verbatim reports and the
resulting 0.2.0 revision are in
[`docs/investigations/2026-10-09-cube/`](docs/investigations/2026-10-09-cube/README.md).
Version 0.3.0 withdraws one investigator claim that 0.2.0 had adopted without
recomputing it, and adds a check for the corrected statement.

Render the initial Active Inference Institute bundle with:

```bash
uv run python -m skillarum run \
  --profile data/sources/active_inference_institute.yaml \
  --backend deterministic
```

Use `--refresh` to fetch new source pages instead of using the acquired bundle
cache. If refreshed content is unchanged, the expensive process-stage draft is
still reused. Use `--force-process` to rerun the selected generator, and
`--target <id>` to select one named target from a profile.

Rebuild the discovery index independently with:

```bash
uv run python -m skillarum index --skills-dir output/skills
```

The `doctor` command checks profile validity, output/cache writeability, the
Ollama `/api/tags` endpoint and configured model, and OpenAI configuration when
the selected profile needs it. Use `--no-network` for local-only checks:

~~~bash
uv run python -m skillarum doctor --profile data/sources/math4wisdom.yaml --output-dir output --json
uv run python -m skillarum cache inspect --output-dir output \
  --profile data/sources/math4wisdom.yaml --json
~~~

## Documentation

Read the [documentation index](docs/README.md) for setup, configuration, source
and trust boundaries, outputs, and verification. The [CLI and workflow
reference](docs/usage.md) covers the commands and generator backends. The
[fixture render guide](docs/rendering.md) produces a separate local research
build and checks the [manuscript](docs/manuscript/README.md).

## Author and publication metadata

The manuscript author is Daniel Ari Friedman, Active Inference Institute,
ORCID [`0000-0001-6232-9096`](https://orcid.org/0000-0001-6232-9096). Release
0.3.1 (release date 2026-10-09) is identified by the version DOI
[`10.5281/zenodo.23271010`](https://doi.org/10.5281/zenodo.23271010), the
repository <https://github.com/docxology/Skillarum>, and the release
<https://github.com/docxology/Skillarum/releases/tag/v0.3.1>. The concept DOI
[`10.5281/zenodo.22663906`](https://doi.org/10.5281/zenodo.22663906) always
resolves to the latest version; release 0.3.0 is
[`10.5281/zenodo.23269108`](https://doi.org/10.5281/zenodo.23269108) and
release 0.2.0 is
[`10.5281/zenodo.22663907`](https://doi.org/10.5281/zenodo.22663907). The
machine-readable citation record is [`CITATION.cff`](CITATION.cff), the full
identifier inventory is in [`docs/publication.md`](docs/publication.md), and
the cover asset is documented with its hash, dimensions, caption, alt text,
and limitations in [`data/cover.yaml`](data/cover.yaml).
`research publication` writes `output/reports/publication-manifest.json`, an
explicit hash inventory of publishable skills, research files, figures, PDF,
and HTML. The current report is selected through
`output/reports/evaluation-manifest.json`; stale evaluation snapshots and
local `AGENTS.md`/`README.md` guidance are excluded. Private caches/runs,
symlinks, and credential markers are rejected and validated.

For release validation, materialize project metadata and require parent-rendered
outputs:

~~~bash
uv run python -m skillarum research publication \
  --output-dir output --project-root . --require-rendered --json
~~~

This hashes the cover, citation record, claims ledger, citation ledger, cover
metadata, and manuscript configuration alongside the generated publication
surface. Command-provider diagnostics contain only redacted command arguments;
API keys and authorization values never enter manifests or cache identities.

The report ID is deterministic for the observation and rating payload. The
envelope's `generated_at` timestamp is intentionally operational provenance,
so repeated evaluation may produce different envelope bytes while retaining
the same report identity and observation content. Do not present the timestamp
as a reproducibility guarantee; compare the report ID, observation hashes, and
publication manifest hashes instead.

Generated packages preserve human-facing paths such as
`output/skills/Math4Wisdom/Three-Minds/` and
`output/skills/Active-Inference-Institute/Institute-Overview/`, while the
frontmatter `name` is the lowercase portable slug required by Codex (for
example `three-minds`). The manifest retains both `requested_skill_name` and
`portable_name`, so target authority is not lost for portability. Verify either
canonical example with Codex’s validator:

```bash
uv run python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  output/skills/Math4Wisdom/Three-Minds
uv run python "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  output/skills/Active-Inference-Institute/Institute-Overview
```

Install and verify a generated package with the supported CLI:

```bash
uv run python -m skillarum install output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex
uv run python -m skillarum drift output/skills/Math4Wisdom/Three-Minds/SKILL.md --harness codex --json
```

The installer stages the full package and its receipt before replacement;
`drift` checks all companion files as well as `SKILL.md`.

For operational details on cache invalidation, provider budgeting, local
Ollama checks, and publication gates, see
[`docs/operations.md`](docs/operations.md).

For an empty-cache refresh and a broader dated inventory of both source websites,
see [the source refresh runbook](docs/source-refresh.md). The full HTML inventory
is retained separately from the seven bounded skill bundles. Harness installation
uses each skill's portable frontmatter name, so a refresh replaces the existing
slug directory rather than creating a differently named copy.

Manuscript results, reporting settings, profile tables, and figure captions are
source-bound; see [the binding contract](docs/manuscript-bindings.md).

Skillarum itself is available as an authored [operator skill](skills/skillarum/SKILL.md)
and a [local MCP server](docs/mcp.md). The operator skill contains software
workflow guidance; the generated website skills retain their separate,
source-bounded provenance contract.

## Citing Skillarum

If you use Skillarum in research or practice, please cite it through
[`CITATION.cff`](CITATION.cff). Plain-text form:

> Daniel Ari Friedman (2026). *Skillarum: Conditionally Reproducible
> Website-to-Agent-Skill Compilation*, version 0.3.1.
> DOI: [10.5281/zenodo.23271010](https://doi.org/10.5281/zenodo.23271010).
> Source: <https://github.com/docxology/Skillarum>

## License

Released under the MIT License; see [`LICENSE`](LICENSE). Copyright (c) 2026
Daniel Ari Friedman, Active Inference Institute.
