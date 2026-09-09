# Skillarum evaluation and publication

Skillarum separates two products: source-bounded generated skills and a
research layer that measures the pipeline. The research layer never adds
scholarly interpretation to a generated `SKILL.md`; it records observations
about persisted artifacts and keeps external literature in the manuscript and
BibTeX ledger.

## Evidence tiers

Every manuscript claim is represented in [`data/claims.yaml`](../data/claims.yaml)
and names its evidence surface:

- `measured`: deterministic fixture or artifact observations;
- `live_case`: an explicitly opted-in snapshot of one of the two example sites;
- `source`: an external paper, specification, or source-page citation;
- `hypothesis` or `pending`: a statement that is not yet publishable as an
  empirical result.

The two example profiles are case studies, not a representative sample of the
web. Fixture-server tests establish implementation behavior but are not live
website evidence. The default report records missingness rather than replacing
missing observations with zeros.

## Reproducible commands

From the project root:

```bash
# Offline aggregation of already persisted runs.
uv run python -m skillarum evaluate --output-dir output --json

# Explicit live acquisition for public profiles.
uv run python -m skillarum evaluate \
  --profile data/sources/math4wisdom.yaml \
  --profile data/sources/active_inference_institute.yaml \
  --backend deterministic --live --refresh --output-dir output --json

# Validate citations, claims, figures, and report integrity.
uv run python -m skillarum research validate \
  --evaluation output/reports/evaluation-summary.json --json

# Produce deterministic SVG figures and optional PNG companions.
uv run python -m skillarum figures \
  --evaluation output/reports/evaluation-summary.json --output-dir output/figures --json

# Resolve manuscript tokens and check figure references.
uv run python -m skillarum research manuscript \
  --evaluation output/reports/evaluation-summary.json --render --json

# Hash and validate the publication surface after parent-template rendering.
uv run python -m skillarum research publication --output-dir output --json
```

CLI settings override profile generation defaults. Credentials are read only
from environment variables. Public live evaluation requires `--live` so that a
research artifact cannot be mistaken for an offline test result.

Origin is stored on each completed target record. Loopback profiles are
`fixture`; public evaluation acquisitions with `--live --refresh` are `live`.
Old records without an origin declaration remain `unknown`, and a later
aggregation flag cannot relabel them. A public cache hit does not count as a
fresh live acquisition. For schema-2 packages, the observation reader additionally binds
the run snapshot to `02_prepare/<target-slug>.json`. Structural package
validity is therefore necessary but not sufficient for provenance-complete
research evidence.

Malformed package manifests remain in the observation stream as invalid,
diagnosable rows. If two persisted rows claim the same observation identity
with different payloads, aggregation fails closed rather than applying a
last-write-wins rule.

The figure registry is schema 4. Every entry carries a stable identifier,
source-data hash, vector and optional raster hashes, generator version, title,
caption, accessible alt text, units, aggregation, sample-size basis, uncertainty
method, limitations, evidence origin, and manuscript references. Captions state
the observed population, denominators, uncertainty policy, and what the plot
cannot establish. The acquisition view separates accepted/rejected/redirected/
canonicalized/duplicate/truncated outcomes; coverage and request-pressure
views make denominators visible; the area catalog makes the two canonical
output namespaces explicit: `Math4Wisdom/` and
`Active-Inference-Institute/`. Human-review figures are intentionally omitted
until two real rater datasets exist; no empty or decorative agreement plot is
published.

## Statistical policy

Reports include counts, rates, medians, ranges, missingness, and sample sizes.
Acquisition request counts use the persisted `request_count` field and are
cross-checkable against events marked `request_attempt: true`; duplicate and
redirect counters use explicit event kinds. A structurally valid package whose
source mapping no longer matches its prepared-corpus snapshot remains
diagnosable but is not provenance-complete.
Small-sample proportions use exact Clopper–Pearson intervals when an interval
is requested. Seeded percentile bootstrap intervals are emitted only for
numerical measurements and counts at the threshold declared by `statistics.DEFAULT_POLICY`. The project does not emit
normal approximations or significance claims for the current case-study scale.
Human review uses a 0–4 ordinal rubric across semantic coverage, procedural
usefulness, verification quality, provenance fidelity, safety, and readability.
Agreement is gated until two distinct rater IDs provide real rows with paired
case IDs; a third rater keeps the status pending rather than silently picking
an arbitrary pair to correlate. A blank template is not data, and one-rater
pilot results remain explicitly labeled as pending. Disagreements require an
auditable adjudication record with both rater IDs, a final score, rationale,
adjudicator, and at least one absolute http(s) evidence URL — the record
constructor enforces the evidence URL, and validation lists records that
merely restate an existing agreement under
`adjudications_without_disagreement` instead of treating them as resolutions.

The artifact strategy is informed by reproducible computational research and
the FAIR principles: records are given stable identifiers, explicit hashes,
portable formats, and inspectable provenance. This is a design orientation,
not a claim of formal FAIR compliance or permanent preservation. A live-site
snapshot remains time-dependent, and source licensing, retention, privacy, and
downstream reuse permissions must be assessed by the operator.

The package manifest also follows the reporting discipline of datasheets and
model cards: it records the intended source scope, observed inputs, generation
context, validation results, limitations, and recommended boundaries of use.
This is an analogy about documentation quality. A Skillarum package is not
a dataset datasheet, not a model card, and not an MCP tool server; it is a
static source-bounded skill artifact that can be installed into compatible
agent runtimes after validation.

## Artifact integrity

Evaluation reports carry a content hash and are accompanied by
`output/reports/evaluation-manifest.json`, which hashes the report and its
summary copy. The publication manifest includes only the report selected by
that integrity manifest; older evaluation snapshots are retained locally but
are not silently published. Figure registry entries hash their source data and
generated SVG or PNG artifact; `figure_registry.manifest.json` hashes the
registry itself. Tampering, path escape, or symlink substitution causes
validation to fail. Local `AGENTS.md` and `README.md` guidance files are not
manuscript publication inputs. Raw caches, credentials, and temporary provider
payloads are not publication inputs.

The report ID hashes observations and ratings and is stable across repeated
aggregation. `generated_at` remains a retrieval-time field in the report
envelope and is deliberately excluded from that identity; its changing value
means byte-for-byte equality of complete report envelopes is not claimed.
Compare report IDs, observation payloads, and publication-manifest hashes when
assessing reproducibility.

The parent template repository remains the final PDF/HTML renderer. Link this
project into the sibling checkout and render explicitly; do not copy the
template engine into this project. The release publication check can require
both configured formats and hashes a materialized cover, citation record,
claims/citation ledgers, cover metadata, and manuscript configuration. Browser rendering, JavaScript execution,
scheduling, hosted APIs, and automatic publication remain outside v1.

The manuscript cover is a conceptual, text-free illustration documented in
`data/cover.yaml`. It is not a data visualization, live-site screenshot, or
claim about agent performance; publication renders must preserve its caption,
alt text, and artifact hash alongside the manuscript metadata.

## Interpretation and missingness

`research build` executes the offline steps above in dependency order and
writes a receipt. PDF/HTML rendering and final publication validation remain
separate gates in [the release checklist](release-checklist.md).

The collector includes completed `rendered` manifests, not failed runs. Stable
run IDs overwrite repeated invocations; the case-plan repetition field is a
plan, not an independent sample count. The package-valid fraction is conditional
on this selected completed set. Exact binomial intervals are model-reference
intervals under independent Bernoulli assumptions, not web-population estimates.
Bootstrap summaries use seed 1729 and 2000 resamples and require at least 20
finite values; nested targets and repeated ratings can violate independence.

Unavailable telemetry is marked in observation `metadata.missing_metrics`;
numerical summaries omit those values and expose `missing_count`. Plot labels
use N/A for unavailable timing or undefined ratios, and a cached draft retains
its original generation timing. These are not full rerun wall-clock measurements.
Weighted kappa is null only when both raters are constant on the same single
category (expected agreement exactly one); a constant rater against a varying
one yields kappa 0, not null.

Pooled ordinal rubric scores are described without bootstrap intervals: multiple rater rows on a shared case are not independent samples. Missing fallback telemetry is excluded from the fallback-rate denominator.

Run/target/page diagnostics keep overlap visible: `run_count`,
`targets_observed_multiple_times`, `max_observations_per_target`,
`unique_source_url_count` versus `source_url_instance_count`, and
`observations_with_complete_telemetry` (the eligible denominator behind
telemetry-based rates). Observations enforce their evidence-origin vocabulary
(`fixture`, `live`, `unknown`) and strict boolean outcome flags at
construction, so aggregation can neither relabel origin nor inflate a
proportion with a truthy non-boolean; private-path blocklists compare path
parts case-insensitively.

The [statistical methods reference](statistics.md) documents strict input
validation and the canonical reporting policy. [Manuscript bindings](manuscript-bindings.md)
links the same policy and verified figure captions into the paper.
