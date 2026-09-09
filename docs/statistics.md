# Statistical methods

This document describes the executable statistical policy of the research
layer and the numerical checks that validate it. The implementation lives in
[`src/skillarum/statistics.py`](../src/skillarum/statistics.py); the report
integration lives in the evaluation portion of
[`src/skillarum/research.py`](../src/skillarum/research.py). If this document
and the code disagree, read the code and fix this document.

## Canonical policy

Every inferential number the evaluation layer publishes is computed under one
validated policy object. The manuscript layer consumes
`skillarum.statistics.DEFAULT_POLICY` for auto-injection; reports embed the
same payload under `summary.policy`, so a reader can see exactly which
configuration produced each interval.

| Field | Default | Meaning |
| --- | --- | --- |
| `confidence` | `0.95` | Two-sided confidence level for exact and bootstrap intervals |
| `bootstrap_minimum_n` | `20` | Smallest sample size that earns a bootstrap interval |
| `bootstrap_seed` | `1729` | Mersenne Twister seed; one instance per call, so intervals are byte-identical across runs |
| `bootstrap_resamples` | `2000` | Number of resamples (`B`) per interval |
| `rating_minimum` | `0` | Inclusive lower bound of the ordinal rating scale |
| `rating_maximum` | `4` | Inclusive upper bound of the ordinal rating scale |

`policy_payload()` additionally reports `interval_method` (`clopper_pearson_exact`)
and `bootstrap_method` (`percentile`). `validate_policy()` rejects incoherent
policies (confidence outside `(0, 1)` or non-finite, non-integer or boolean
integer fields, `bootstrap_minimum_n < 2`, `bootstrap_resamples < 1`, or a
rating scale violating `0 <= rating_minimum < rating_maximum`).
`policy_from_mapping()` builds a policy from a partial mapping and rejects
unknown keys; report computation itself is
performed exclusively under `DEFAULT_POLICY`, which keeps the
`exact_95_interval` key labels truthful and makes the embedded payload a
complete description of what ran.

## Failure conventions

Two clearly separated failure modes:

- **Undefined for the data** returns `None`: an empty or below-floor sample,
  a proportion with a zero denominator, an exact-binomial request with a
  boundary confidence level (`0` or `1`), or kappa with expected agreement one.
  Callers must render `None` as "not estimable", never as zero.
- **Invalid usage** raises `ValueError`: non-integer or boolean binomial
  counts, non-finite samples, an unknown bootstrap statistic, an inconsistent
  ordinal scale, ratings outside the declared scale, or a non-positive
  resampling configuration.

The legacy exact-binomial API returns `None` for invalid boundary confidence;
the bootstrap API rejects confidence outside `(0, 1)` with `ValueError`.

Validity checks run *before* the small-sample early return, so a non-finite
sample is never silently reported as "too small to estimate".

## Methods

### Exact binomial intervals

`exact_binomial_interval(successes, total, confidence)` returns a
Clopper–Pearson interval: the lower limit solves `P(X ≥ successes | p) = (1 −
confidence) / 2` and the upper limit solves `P(X ≤ successes | p) = (1 −
confidence) / 2`. The implementation inverts the regularized incomplete beta
function by bisection over a Lentz-style continued fraction, with no scipy
dependency. Boundary counts use closed forms: for `x = 0` the upper limit is
`1 − (α/2)^{1/n}`; for `x = n` the lower limit is `(α/2)^{1/n}`.

Validation: `tests/test_statistics.py` checks boundary endpoints against those
closed forms and interior endpoints against independent finite binomial-tail
sums built on `math.comb`, solved by bisection. Fractional and boolean counts
are rejected as caller bugs; degenerate requests (`total = 0`, `successes >
total`, boundary confidence) return `None`.

Citation: Clopper, C. J., and E. S. Pearson. "The Use of Confidence or
Fiducial Limits Illustrated in the Case of the Binomial." *Biometrika* 26,
no. 4 (1934): 404–413. doi:10.1093/biomet/26.4.404.

### Percentile bootstrap intervals

`bootstrap_interval(values, statistic=…, confidence=…, seed=…, resamples=…,
minimum_n=…)` resamples with replacement `B = resamples` times under one
seeded random generator and reports the order statistics of the resample
distribution at `int(tail · B)` and `int((1 − tail) · B) − 1`, clamped into
range, where `tail = (1 − confidence) / 2`. Samples with fewer than
`minimum_n` finite values return `None`.

Percentile intervals are approximate; no finite-sample coverage calibration
is claimed or implied. The floor (`bootstrap_minimum_n = 20`) is a reporting
rule, not a coverage guarantee. Applies to numerical measurements and counts
alike — a mean is meaningful for both; pooled ordinal ratings are excluded
and belong in the ordinal summary below. `summarize_observations` lists each
of the four summarized numeric metrics (`page_count`, `request_count`,
`response_bytes`, `generation_duration_ms`) whose usable sample is non-empty
but below the floor under `summary.small_sample_metrics`; a field with no
usable values at all is reported under `telemetry_missing` instead, so
captions can decline to quote intervals.

Citation: Efron, B. "Bootstrap Methods: Another Look at the Jackknife." *The
Annals of Statistics* 7, no. 1 (1979): 1–26. doi:10.1214/aos/1176344552.

### Numeric summaries

`numeric_summary(values)` reports `n`, range, mean, median, quartiles
(linear interpolation between order statistics), sample standard deviation
(`None` for `n = 1`), and the bootstrap mean interval (`None` below the
floor or when `bootstrap=False`). Non-finite values raise. The summary
applies to numerical measurements and counts; moments of ordinal rating
pools are not reported as if they were interval data.

### Ordinal rating distributions

`ordinal_summary(values, minimum=…, maximum=…)` reports the empirical
distribution per category (string-keyed for JSON safety), the modal
category or categories with ties, and the modal share. Medians are also valid
ordinal summaries. `review_summary` retains descriptive moments of the
assigned rubric scores alongside their distribution; a score average does
not establish equal spacing of the latent construct.

### Rater agreement

`weighted_cohen_kappa(first, second, minimum=…, maximum=…)` computes
linearly weighted Cohen's kappa for paired ordinal ratings: disagreements
one category apart earn partial credit. It returns `None` when no case is
rated by both raters or when expected agreement equals one (both raters use
the same single category throughout). One constant rater paired with a
varying rater instead yields zero kappa; constant marginals alone do not
imply an undefined statistic.
`review_summary` gates agreement entirely until exactly two raters share at
least one case, lists criteria whose kappa is undefined under
`agreement_undefined`, and never pools ratings across raters to manufacture
an interval.

Citation: Cohen, J. "Weighted Kappa: Nominal Scale Agreement with Provision
for Scaled Disagreement or Partial Credit." *Psychological Bulletin* 70,
no. 4 (1968): 213–220.

## Missingness and denominators

Observations carry `metadata.missing_metrics` naming telemetry fields that
the underlying run never recorded. `summarize_observations` excludes those
fields from both the numerator and the denominator of the affected rate
(`fallback_used` is the load-bearing case: a run without generation attempts
has no fallback outcome, so it must not enter the fallback denominator as a
failure). Every proportion payload reports `successes`, `total`, `rate`, and
the exact interval so the denominator is always visible next to the rate.
`telemetry_missing` counts missing observations per field.

Overlapping selected runs stay visible instead of being silently pooled:
`run_count` counts distinct run ids, `targets_observed_multiple_times` and
`max_observations_per_target` expose targets measured by more than one run,
and `unique_source_url_count` contrasts with `source_url_instance_count` so
page overlap across observations is distinguishable from summed page counts.
`observations_with_complete_telemetry` counts the eligible denominator
behind the telemetry-based rates. None of these keys implies independence
between repeated observations.

Observation contracts are validated at construction: `source` must be one of
`fixture`, `live`, `unknown`, and the boolean outcome fields
(`package_valid`, `provenance_complete`, `required_sections_valid`,
`unsafe_source_preserved`, `fallback_used`) must be true booleans, so a
truthy integer cannot inflate a proportion, and a later aggregation step
cannot relabel evidence origin. Private-path blocklists
(`.cache`, `runs`) compare path parts case-insensitively, closing the
case-variant bypass on case-insensitive filesystems.

## Sampling-design boundaries

`summary.sampling_design` states the caveat in the payload itself:
observations are selected completed run-target snapshots, repeated
invocations overwrite stable run identities, and intervals require
independence assumptions that a hand-selected corpus does not establish.
Intervals are reference quantities under the stated sampling model; the
selected corpus does not establish their population coverage. Fixture observations are never presented
as live-site evidence; `summary.source_types` keeps the split visible.

## Report integrity

`EvaluationReport` persists typed rating rows (`ratings`) alongside
observations, and `artifact_sha256` covers the full payload including those
rows. On load, `load_evaluation_report`:

1. verifies the payload hash when present;
2. recomputes `summarize_observations(observations)` and rejects any stored
   top-level summary key that disagrees;
3. rejects any review claim (`rating_count`, rater counts, paired cases,
   agreement entries, a `complete` status, or a `complete`
   `rating_status` envelope) when no rating rows are present — including
   forgeries that recompute the payload hash, because the semantic gates run
   after the hash gate;
4. recomputes `review_summary(ratings)` and rejects stored review keys that
   disagree, and rejects a `rating_status` envelope that disagrees with the
   rederived status.

Current reports must carry every rederived summary and review field, with one
documented migration: a current-format report written before the additive
run/target/page diagnostics existed is reconstructed for exactly those keys
(`ADDITIVE_SUMMARY_KEYS` in `research.py`) and rehashed, because the merged
content differs from the stored payload. Any other missing key is rejected.
Extra unknown summary keys are tolerated but are not independently
recomputed; the payload hash authenticates them, and the hash does not prove
truth. Consumers read only named keys. Legacy reports without a `ratings`
member have missing fields reconstructed from observations, with a new
content hash for the upgraded representation. Neither path passes missing
counts to presentation code as fabricated zeros.
That migration is the only silent-looking reconstruction: everything else in
a current-format summary must match the recomputation exactly.

## Compatibility

- All public statistics remain importable from both
  `skillarum.statistics` (owner) and `skillarum.research` (re-export); the
  re-exports are the same objects.
- Reports written before this change remain readable if they are pending with
  no ratings: the loader verifies stored fields and reconstructs missing ones. A
  legacy report whose summary claims ratings but which carries no rating
  rows is now rejected with an explicit error instead of being trusted;
  re-run `research report` to regenerate it with persisted rows.
- New summary keys (`policy`, `small_sample_metrics`, per-criterion
  `distribution`/`mode`/`mode_share`, `agreement_undefined`) are additive.
- Existing behavior pinned by tests is preserved: `None` for degenerate
  boundary requests (`exact_binomial_interval(0, 0)`, `(2, 1)`,
  `confidence=1.0`; short bootstrap samples), pinned quartile values, and
  `weighted_cohen_kappa({}, {})` returning `None`.

## Verification

From the project root:

```bash
uv run --extra dev --extra research pytest tests/test_statistics.py --no-cov
```

The oracle helpers in `tests/test_statistics.py` are independent of the
implementation: closed forms at CP boundaries, finite binomial-tail sums via
`math.comb` in the interior, and hand-computed kappa values. Large-`n`
endpoints — including `n = 100000` and confidence levels `0.90`/`0.99` — are
verified against stable exact binomial tail sums (lgamma-based PMF start with
complement recursion, never starting from an underflowed term) by the
defining Clopper–Pearson tail equations. Negative controls cover
fraction/boolean counts, non-finite samples, invalid scales, strict
observation contracts, self-consistent report forgeries, and legacy-report
readability.

## See also

- [`evaluation.md`](evaluation.md) — evidence tiers and evaluation workflow
- [`manuscript-bindings.md`](manuscript-bindings.md) — parameter injection
  and numeric-prose validation
- [`../src/skillarum/AGENTS.md`](../src/skillarum/AGENTS.md) — module map
