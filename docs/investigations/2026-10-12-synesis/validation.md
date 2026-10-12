# Validation record: cube skill 0.4.0

Observed October 12, 2026, in the GitVault Skillarum checkout.
These receipts concern the authored skill revision, not a new software
release, independent investigator audit, or Zenodo publication.

| Check | Observed result |
| --- | --- |
| Original checker before editing | 21 checks passed |
| Revised checker | 23 checks passed |
| Focused cube tests | 4 passed, including rejection controls |
| Full development/research suite | 576 passed, 2 skipped; 92.29% coverage; exit 0 |
| Clean staged snapshot, no pre-existing disposable outputs | 576 passed, 2 skipped; 92.03% coverage; exit 0 |
| Ruff check and format, src/tests/authored checker | Passed after formatting |
| Python compilation | Passed |
| Portable package validation | 537 packages passed |
| Codex quick validator, both area namespaces and authored skills | 537 packages passed |
| Offline research build | Ledgers, bibliography, figures, manuscript, archives, hydration, bindings passed |
| Parent render | PDF, HTML, EPUB passed; 22-page combined PDF |
| Publication manifest | 1,136 artifacts validated after render |
| Research validate | Passed after publication manifest refresh |
| Parent stage 04 | Exit 0; rendered provenance: 61 source, 18 config, 7,122 output files |
| Authored Markdown links | 10 local links resolved |
| Ledger ID uniqueness | 14 source and 23 mathematics entries, no duplicate IDs |
| PDF/HTML inspection | All 22 PDF pages inspected in a contact sheet, two figure pages enlarged; HTML has 11 resolved images and no unresolved tokens |

The clean snapshot was archived from staged tree
`1f9dddad41c29fb14b98f55dccc14d8b1305b42a` before this receipt addition.
It used the checkout's installed development/research interpreter via
`uv run --no-project --python ... python -m pytest tests/ --cov=src --cov-fail-under=90 -q`.
Generated skills tracked by Git were present; disposable research outputs
and crawl caches were absent. The differing coverage totals are reported
separately rather than treating the working checkout as a clean snapshot.

Rendered artifact SHA-256:

- PDF: `5878f2883e342500e551acd7a4b6e5fd36e4c0bb29d37fbff00963a45097a045`
- HTML: `c88021cd98268516d82cf208e503f70439a121cbf2ecbeb42f6051fc30c52e26`

## Negative controls

M22 rejects a missing triple, duplicated triple, the 48 ordinary flags, and a
24-flag subset. M23 rejects swapping one standard and one dual basis vector
between the vector module's two blocks: dimensions stay 4+4 and the total
character stays unchanged, but root-operator closure fails. A real subprocess
running a copied checker with one transverse triple removed exits 1, emits
`ok: false`, and identifies M22 as the failing claim.

## Failures and external limitations retained

- Initial Ruff format check found two files needing formatting; they were
  formatted and the subsequent check passed.
- A publication validation was run while rendering was in progress. It
  exited 1 with stale artifact hashes and temporarily absent PDF/HTML. After
  rendering completed, publication manifest regeneration and research
  validation both exited 0. The early failure is not counted as a pass.
- The release checklist's `working/Skillarum` path is obsolete in this
  workspace. The existing parent lifecycle link `ongoing/docxology/Skillarum`
  resolves to this checkout and was used successfully.
- `check_signposts.py` is absent from the current template and sidecar. Its
  historical check is unavailable; local authored links and guides are checked
  directly, without claiming that this replaces the missing parent script.
- Parent stage 04 reports 11 noncritical missing-image diagnostics against
  unhydrated manuscript-relative paths, while its figure registry validates
  all 11 figure references and enabled rendered artifacts. It also prints
  `05_evaluation.md:99: unsupported number -1`, despite marking the evidence
  registry passed. The parent warns about config key `manuscript_bindings`
  and displays a historical September timestamp in its summary. Those
  pre-existing parent diagnostics are not promoted to clean scholarly proof.
- Two poster preview snapshots timed out; the public PNG was downloaded and
  inspected directly. The linked shared conversation timed out and was not
  inspected. Synesis's original computation script was not provided.

The original investigator reports and archived release identifiers remain
intact. No generated website skills, scientific manuscript claims, or
credentials are part of this revision.
