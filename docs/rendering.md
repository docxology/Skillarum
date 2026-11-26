# Local fixture and manuscript render

Use a fresh Skillarum checkout. The manuscript source lives in
[`docs/manuscript/`](manuscript/README.md). A clean checkout has the published
package catalog and source ledgers. Hydration also needs at least one completed
run snapshot under `output/runs/`.

## Create fixture evidence

From the Skillarum root, install the locked development and research extras.
The example serves the test suite's authored fixture on loopback and runs only
its benign `/page` target. Robots rules, the same-origin restriction, and the
normal response budget still apply. The loopback allowance belongs only to this
temporary test profile. Extracted content and the generated skill are data.

```bash
uv sync --locked --python 3.14 --extra dev --extra research
uv run --locked --extra dev --extra research python - <<'PY'
from contextlib import contextmanager
from pathlib import Path
from runpy import run_path
from shutil import copytree
from tempfile import TemporaryDirectory

from skillarum.pipeline import run_profile_from_path

serve_fixture = contextmanager(run_path("tests/conftest.py")["fixture_server"].__wrapped__)
with TemporaryDirectory() as tmp, serve_fixture() as url:
    work = Path(tmp)
    profile = work / "profile.yaml"
    profile.write_text(
        f"id: fixture\nname: Local fixture\nbase_url: {url}\n"
        "crawl:\n  allow_private_hosts: true\n  requests_per_second: 20\n"
        "targets:\n  - id: page\n    name: Fixture Page\n    urls: ['/page']\n",
        encoding="utf-8",
    )
    staged = work / "output"
    run_profile_from_path(profile, output_dir=staged, backend="deterministic")
    copytree(staged / "runs", Path("output/runs"))
PY
uv run --locked --extra research python -m skillarum research build --output-dir output --json
```

The copy requires an unused `output/runs/` path so a fixture build cannot mix
with previous observations. The published catalog stays in place. The research
command writes the evaluation summary, figures, hydrated Markdown, and binding
receipt under `output/`. The observation should have origin `fixture`; a
loopback port, timestamps, and timing can vary between fresh runs. Reuse the
same run snapshot when comparing report identities. This evidence exercises
extraction, package integrity, and the paper build. Public-site results and
human ratings require their own retained evidence. The fixture render is a
local verification artifact and carries the manuscript source metadata. The
published DOI resolves to the archived release with its own evidence.

## Render and validate with Template

Install Template's dependencies using its
[pinned setup guide](https://github.com/docxology/template/blob/87704feae0a4490ef7dad9c931d268e8c30273c2/docs/RUN_GUIDE.md).
The local verification used Python 3.14, Pandoc 3.14, pandoc-crossref
0.3.26, and a LaTeX distribution. In a separate parent checkout, register the
Skillarum path under `projects/working/` after creating the project-local `.venv` in the first step. Template uses
that environment for the hydration hook. Match pandoc-crossref to the
installed Pandoc version.

```bash
# Run from the root of the separate docxology/template checkout.
git switch --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
mkdir -p projects/working
ln -s /absolute/path/to/Skillarum projects/working/Skillarum
uv run --locked python scripts/pipeline/stage_03_render.py --project working/Skillarum
uv run --locked python scripts/pipeline/stage_04_validate.py --project working/Skillarum
```

Run the local research build first. Template Stage 03 consumes the hydrated
tree under `output/manuscript/` and writes the combined PDF under
`output/pdf/` and the HTML under `output/web/`. Stage 04 writes the
validation and rendered-provenance receipts under `output/reports/`.
Inspect the numbered sections, bibliography, cover, registered figures,
and evidence-origin labels. See the [release checklist](release-checklist.md)
for release-only checks and the [publication record](publication.md) for prior
DOI-backed artifacts.
