# Evaluation records

`cases.yaml` is the declarative live-matrix plan. Each entry carries `id`,
`label`, `profile_id`, `target_id`, `source` (the intended evidence origin —
`live` for all seven), and `repetitions`; the file states intent and does not
claim that a run occurred. It declares seven cases: `math-three-minds`,
`math-three-minds-exposition`, `math-minds-research`, `aii-institute-overview`,
`aii-foundations`, `aii-programs`, and `aii-projects`.

Rating files use the CSV schema emitted by the command below. Pass case ids
from `cases.yaml`:

```bash
uv run python -m skillarum research ratings-template \
  --output data/evaluation/ratings.csv \
  --case math-three-minds --case aii-institute-overview --json
```

Two independent completed rating files are required before agreement is
reported. Pass both files by repeating `--ratings` on `evaluate` or
`research validate`; agreement remains pending if the files have no overlapping
case IDs. Do not fill the tracked plan with invented or placeholder scores.
Ratings must include evidence notes or source URLs for substantive judgments.
Disagreements are resolved in a JSON adjudication file containing the case,
criterion, two rater IDs, final 0–4 score, adjudicator ID, rationale, and
evidence URLs. The validator checks that every adjudication refers to actual
rows in the associated rating files. When `--ratings` is omitted for an
adjudication check, the conventional sibling `ratings.csv` is used only as a
compatibility fallback.

See [`AGENTS.md`](AGENTS.md) for the full `cases.yaml` schema, the case/profile
mapping, and the rating and adjudication rules.
