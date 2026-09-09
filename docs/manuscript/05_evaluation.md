# Evaluation design and results {#sec:evaluation}

The evaluation is deliberately divided into three evidence classes. Local
fixture observations test behavior under controlled redirects, robots rules,
oversized streaming responses, transient failures, prompt injection, cache
corruption, and subprocess boundaries. Live observations exercise the configured
public source profiles and their expanded declarative bundles. Human ratings
assess the usefulness and safety of the resulting skills. Fixture evidence is
not presented as live-site evidence, and live case studies are not treated as
population samples.

## Observation set and estimands

The current report contains {{OBSERVATION_COUNT}} completed observations across
{{TARGET_COUNT}} target rows. {{LIVE_OBSERVATION_COUNT}} are labeled live. The
package-valid rate is {{PACKAGE_VALID_RATE}}. The run matrix recorded
{{FALLBACK_COUNT}} fallback observations, {{TRUNCATED_PAGES}} truncated pages,
and a human-review status of {{RATING_STATUS}}. Evidence labels describe persisted acquisition declarations; a later `--live`
flag cannot upgrade historical observations. Older runs without declarations
remain `unknown`. Telemetry availability is recorded separately from stored
compatibility counters; an unavailable metric is not an observed zero.

The primary observational unit is a completed run-target pair: one selected
profile target, one acquisition/preparation/generation/validation path, and
one rendered package. The collector selects manifests whose state is `rendered`;
failed runs remain in operational diagnostics and are excluded from these rates.
Consequently, package validity is conditional on completion, not an end-to-end
success probability. Page records and request attempts
are nested observations within that unit, not independent replicates. Thus,
the live matrix's target and observation counts describe a bounded case-study
design; they must not be read as a sample of independent websites or as a
site-wide estimate. Repeated live runs would be needed before treating an
observation-level rate as more than descriptive operational evidence.

Recorded generator backends: {{BACKENDS_OBSERVED}}. The package-valid numerator
is {{PACKAGE_VALID_COUNT}} among {{OBSERVATION_COUNT}} completed records;
fallback telemetry is available for {{FALLBACK_ELIGIBLE_COUNT}} records.
The distinction between those denominators is preserved in every summary.

## Acquisition and operational diagnostics

Figure [-@fig:acquisition-funnel] reports acquisition outcomes by source area.

![{{FIGURE_ACQUISITION_FUNNEL_CAPTION}}](../output/figures/acquisition-funnel.png){#fig:acquisition-funnel}

Figure [-@fig:provider-fallback-outcomes] summarizes provider fallback, failure, and retry counts per selected backend.

![{{FIGURE_PROVIDER_FALLBACK_OUTCOMES_CAPTION}}](../output/figures/provider-fallback-outcomes.png){#fig:provider-fallback-outcomes}

Figure [-@fig:generation-latency] plots the individual generation-latency observations.

![{{FIGURE_GENERATION_LATENCY_CAPTION}}](../output/figures/generation-latency.png){#fig:generation-latency}

Figure [-@fig:provenance-completeness] counts observations passing each
integrity check separately; these checks evaluate the provenance-completeness
predicate of [@eq:lineage].

![{{FIGURE_PROVENANCE_COMPLETENESS_CAPTION}}](../output/figures/provenance-completeness.png){#fig:provenance-completeness}

Figure [-@fig:coverage-truncation] compares source-mapping and truncation percentages per area.

![{{FIGURE_COVERAGE_TRUNCATION_CAPTION}}](../output/figures/coverage-truncation.png){#fig:coverage-truncation}

Figure [-@fig:request-pressure] reports request pressure per accepted page.

![{{FIGURE_REQUEST_PRESSURE_CAPTION}}](../output/figures/request-pressure.png){#fig:request-pressure}

Figure [-@fig:area-catalog] tabulates the skill catalog by declared source area.

![{{FIGURE_AREA_CATALOG_CAPTION}}](../output/figures/area-catalog.png){#fig:area-catalog}

If two rating files with distinct rater IDs contain overlapping cases, the registry also
emits the `human-review-rubric` figure. That conditional figure reports criterion-wise
descriptive scores on the {{RATING_MINIMUM}}–{{RATING_MAXIMUM}} rubric and is withheld
when agreement is pending; no empty agreement plot is manufactured for the current package.

## Statistical policy

The executable statistical policy supplies the following settings to both
the analysis and this manuscript. Changing a setting requires rebuilding
the report, figures, and manuscript together.

{{STATISTICAL_POLICY_TABLE}}

Rates are reported with numerator, denominator, missingness, and sample size.
Exact Clopper–Pearson intervals [@clopper-pearson] are provided as binomial-model reference
intervals, assuming independent Bernoulli trials with a common probability.
The selected, nested case-study records do not establish those assumptions.
These intervals therefore do not quantify uncertainty for the web as a
population, and page-level intervals are not cluster-adjusted. Seeded
percentile bootstrap intervals, using the nonparametric resampling framework
of Efron [@efron-bootstrap], are used for numerical measurements and counts with at
least {{BOOTSTRAP_MINIMUM_N}} finite observations with the fixed seed {{BOOTSTRAP_SEED}} and {{BOOTSTRAP_RESAMPLES}} resamples; otherwise the report remains descriptive. No normal
approximation, significance test, or causal claim is made for the initial
case-study matrix. Area-level ratios are labeled as ratios of sums, and
different-denominator percentages are not presented as a decomposition.

For $x$ recorded successes among $n>0$ eligible observations, let
$B^{-1}_{a,b}(q)$ denote the $q$ quantile of a Beta$(a,b)$ distribution.
With $\alpha={{ALPHA}}$, the implemented interval endpoints are

$$
\begin{aligned}
L &= \begin{cases}0 & x=0,\\ B^{-1}_{x,n-x+1}(\alpha/2) & x>0,\end{cases} \\
U &= \begin{cases}1 & x=n,\\ B^{-1}_{x+1,n-x}(1-\alpha/2) & x<n.\end{cases}
\end{aligned}
$$ {#eq:binomial-interval}

For $n=0$, the interval is unavailable. The bootstrap's $n\ge {{BOOTSTRAP_MINIMUM_N}}$ rule is an
implementation reporting threshold; it does not establish independence or
interval coverage. Its empirical distribution resamples the observed values,
so a larger number of resamples cannot repair a biased or dependent sample.

The following table reports the actual eligible denominators and
{{CONFIDENCE_PERCENT}} reference intervals from [@eq:binomial-interval].
Source coverage counts page mappings; the other rows count completed target
records, except that unavailable fallback telemetry is excluded. Intervals
are conditional on the binomial model and do not correct shared-source
dependence or selection into the completed-record set.

When at least two completed observations record a source-URL list, the figure
registry also emits a source-overlap panel reporting the exact shared URLs
between target pairs, with each target's own URL count on the diagonal and
measured zeros printed explicitly; a target whose list was not recorded
appears as unavailable rather than zero. Shared pages are the concrete
dependence behind the model-reference caveat; the panel is withheld when
fewer than two observations record lists, and no synthetic overlap is
manufactured.

{{PROPORTION_TABLE}}

Figure [-@fig:proportion-intervals] shows those same row-specific estimates
and eligible denominators. Its horizontal intervals provide a reference for
the binomial model; they do not turn this selected observation set into an
independent sample.

![{{FIGURE_PROPORTION_INTERVALS_CAPTION}}](../output/figures/proportion-intervals.png){#fig:proportion-intervals}

Operational telemetry is also reported in its recorded units. Missing
observations do not enter the median or range. Response-byte totals describe
the recorded transport telemetry, while generation durations aggregate
provider attempts; these measures do not establish cost or model quality.
When every recorded backend is deterministic, generation-duration telemetry
measures in-process extraction rather than provider latency, so a zero median
is a recorded value rather than a missing measurement.

{{TELEMETRY_TABLE}}

## Human review

The current report contains {{REVIEW_RATER_COUNT}} distinct rater identifiers
and {{REVIEW_PAIRED_CASE_COUNT}} shared cases. This status is an evidence gate,
not a substitute for recruiting independent reviewers or specifying their
training and adjudication procedure.

Raters score {{REVIEW_CRITERIA}} from {{RATING_MINIMUM}} to {{RATING_MAXIMUM}}. Each score requires
an evidence note and source URL. Agreement is computed only when two distinct
rater IDs provide overlapping case rows, using the persisted weighted Cohen
kappa values [@cohen-weighted-kappa]. Until two real rating files exist, agreement remains pending
and no inter-rater statistic or score plot is reported. A single-author pilot,
if later supplied, will remain labeled pilot data rather than being silently
promoted to two-rater evidence. Disagreements require an adjudication record
that retains both rater IDs, the final score, rationale, adjudicator, and
evidence URLs. Rater independence must be established through study design; different identifiers do not verify independent judgments.

For paired counts $n_{ij}$ on categories $i,j\in\{ {{RATING_CATEGORIES}} \}$, let
$p_{ij}=n_{ij}/n$, $p_{i+}=\sum_jp_{ij}$, and $p_{+j}=\sum_ip_{ij}$.
The implementation uses linear agreement weights:

$$
\begin{aligned}
w_{ij} &= 1-\frac{|i-j|}{ {{RATING_SPAN}} }, \\
p_o &= \sum_{i,j}w_{ij}p_{ij}, \\
p_e &= \sum_{i,j}w_{ij}p_{i+}p_{+j}, \\
\kappa_w &= \frac{p_o-p_e}{1-p_e}.
\end{aligned}
$$ {#eq:weighted-agreement}

Only shared case IDs enter $n$. Unpaired rows contribute descriptive scores
but cannot contribute to paired agreement. Linear weights treat adjacent
category disagreements equally; that is a rubric convention rather than a
claim that the latent constructs form an interval scale.

When both raters use the same category on every paired case, weighted kappa
is undefined because expected agreement is one. The report stores `null` in
that case, not perfect chance-corrected agreement. Exact agreement and the
paired-case count remain interpretable descriptive quantities.

Stable run identities overwrite repeated invocations of the same configuration.
A repetition count in the case plan does not create independent samples; a
future repeated-run study must retain separate acquisitions and model the
shared page, target, profile, and provider dependencies.

Pooled ordinal rubric scores are described without bootstrap intervals: multiple rater rows on a shared case are not independent samples. Missing fallback telemetry is excluded from the fallback-rate denominator.
