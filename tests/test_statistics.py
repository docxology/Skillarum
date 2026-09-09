"""Statistical policy, primitives, and report-integrity tests.

Oracles are independent of the implementation: Clopper–Pearson endpoints are
checked against closed forms at the boundaries and finite binomial-tail sums
via ``math.comb`` in the interior. No mocks; everything runs in-process.
"""

import json
import math

import pytest

from skillarum.research import (
    DEFAULT_POLICY,
    StatisticalPolicy,
    EvaluationObservation,
    ReviewRating,
    bootstrap_interval,
    build_evaluation_report,
    exact_binomial_interval,
    load_evaluation_report,
    numeric_summary,
    ordinal_summary,
    policy_from_mapping,
    policy_payload,
    review_summary,
    summarize_observations,
    validate_policy,
    weighted_cohen_kappa,
    write_evaluation_report,
)
from skillarum.statistics import (
    DEFAULT_POLICY as STATISTICS_DEFAULT_POLICY,
    exact_binomial_interval as statistics_exact_binomial_interval,
)
from skillarum.utils import sha256_json


def _cp_lower_tail(p: float, successes: int, total: int) -> float:
    """P(X >= successes | p) by direct summation; independent of the module."""
    return sum(
        math.comb(total, k) * p**k * (1.0 - p) ** (total - k)
        for k in range(successes, total + 1)
    )


def _cp_upper_tail(p: float, successes: int, total: int) -> float:
    """P(X <= successes | p) by direct summation; independent of the module."""
    return sum(
        math.comb(total, k) * p**k * (1.0 - p) ** (total - k)
        for k in range(successes + 1)
    )


def _cp_endpoint_by_bisection(
    successes: int, total: int, endpoint: str, confidence: float = 0.95
) -> float:
    alpha_tail = (1.0 - confidence) / 2.0
    solve = _cp_lower_tail if endpoint == "lower" else _cp_upper_tail
    low, high = 0.0, 1.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if endpoint == "lower":
            # P(X >= x | p) increases in p: above target => above endpoint.
            if solve(middle, successes, total) > alpha_tail:
                high = middle
            else:
                low = middle
        else:
            # P(X <= x | p) decreases in p: above target => below endpoint.
            if solve(middle, successes, total) > alpha_tail:
                low = middle
            else:
                high = middle
    return (low + high) / 2.0


def _observation(case_id: str = "case", **overrides) -> EvaluationObservation:
    fields = {
        "observation_id": f"obs-{case_id}",
        "case_id": case_id,
        "source": "fixture",
        "profile_id": "profile",
        "target_id": "target",
        "run_id": "run",
        "observed_at": "2026-01-01T00:00:00+00:00",
        "page_count": 1,
        "request_count": 2,
        "accepted_pages": 1,
        "rejected_requests": 1,
        "redirect_count": 0,
        "canonical_count": 0,
        "duplicate_count": 0,
        "truncated_pages": 0,
        "response_bytes": 10,
        "cache_hits": 0,
        "provider_attempts": 1,
        "provider_failures": 0,
        "retry_count": 0,
        "fallback_used": False,
        "selected_backend": None,
        "generator": "deterministic",
        "generation_duration_ms": 5,
        "artifact_sha256": "a" * 64,
        "skill_sha256": "b" * 64,
        "package_valid": True,
        "provenance_complete": True,
        "required_sections_valid": True,
        "unsafe_source_preserved": True,
    }
    fields.update(overrides)
    return EvaluationObservation(**fields)


# --- canonical policy ------------------------------------------------------


def test_default_policy_is_the_legacy_call_site_configuration():
    assert DEFAULT_POLICY == StatisticalPolicy(
        confidence=0.95,
        bootstrap_minimum_n=20,
        bootstrap_seed=1729,
        bootstrap_resamples=2000,
        rating_minimum=0,
        rating_maximum=4,
    )
    assert DEFAULT_POLICY is STATISTICS_DEFAULT_POLICY
    assert validate_policy(DEFAULT_POLICY) is DEFAULT_POLICY


def test_policy_payload_is_structured_and_validated():
    payload = policy_payload()
    assert payload == {
        "confidence": 0.95,
        "bootstrap_minimum_n": 20,
        "bootstrap_seed": 1729,
        "bootstrap_resamples": 2000,
        "rating_minimum": 0,
        "rating_maximum": 4,
        "interval_method": "clopper_pearson_exact",
        "bootstrap_method": "percentile",
    }


@pytest.mark.parametrize(
    "override",
    [
        {"confidence": 1.0},
        {"confidence": 0.0},
        {"bootstrap_minimum_n": 1},
        {"bootstrap_minimum_n": 0.5},
        {"bootstrap_resamples": 0},
        {"bootstrap_seed": True},
        {"rating_minimum": 2, "rating_maximum": 2},
        {"rating_minimum": 4, "rating_maximum": 0},
        {"rating_minimum": -1, "rating_maximum": 4},
        {"rating_maximum": 4.0},
    ],
)
def test_validate_policy_rejects_incoherent_policy(override):
    values = {
        "confidence": 0.95,
        "bootstrap_minimum_n": 20,
        "bootstrap_seed": 1729,
        "bootstrap_resamples": 2000,
        "rating_minimum": 0,
        "rating_maximum": 4,
        **override,
    }
    with pytest.raises(ValueError, match="policy"):
        validate_policy(StatisticalPolicy(**values))


def test_policy_from_mapping_partial_and_rejects_unknown_fields():
    policy = policy_from_mapping({"confidence": 0.9, "bootstrap_seed": 7})
    assert policy == StatisticalPolicy(
        confidence=0.9,
        bootstrap_minimum_n=20,
        bootstrap_seed=7,
        bootstrap_resamples=2000,
        rating_minimum=0,
        rating_maximum=4,
    )
    assert policy_from_mapping(None) == DEFAULT_POLICY
    with pytest.raises(ValueError, match="unknown statistical policy fields"):
        policy_from_mapping({"confidence_level": 0.9})


def test_research_reexports_are_the_statistics_objects():
    assert exact_binomial_interval is statistics_exact_binomial_interval


# --- exact binomial (Clopper–Pearson) --------------------------------------


def test_cp_boundaries_match_closed_forms():
    alpha_tail = 0.025
    for total in (1, 2, 5, 10, 50, 200):
        lower, upper = exact_binomial_interval(0, total)
        assert upper == pytest.approx(1.0 - alpha_tail ** (1.0 / total), abs=1e-12)
        assert lower == 0.0
        lower, upper = exact_binomial_interval(total, total)
        assert lower == pytest.approx(alpha_tail ** (1.0 / total), abs=1e-12)
        assert upper == 1.0


@pytest.mark.parametrize(
    ("successes", "total"), [(1, 10), (5, 10), (3, 17), (12, 40), (7, 50)]
)
def test_cp_interior_endpoints_match_finite_binomial_tail_oracle(successes, total):
    lower, upper = exact_binomial_interval(successes, total)
    assert lower == pytest.approx(
        _cp_endpoint_by_bisection(successes, total, "lower"), abs=1e-9
    )
    assert upper == pytest.approx(
        _cp_endpoint_by_bisection(successes, total, "upper"), abs=1e-9
    )
    assert lower < successes / total < upper


def test_cp_rejects_fractional_and_boolean_counts():
    with pytest.raises(ValueError, match="integers"):
        exact_binomial_interval(0.5, 10)
    with pytest.raises(ValueError, match="integers"):
        exact_binomial_interval(True, 10)
    with pytest.raises(ValueError, match="integers"):
        exact_binomial_interval(2.0, 10)
    with pytest.raises(ValueError, match="integers"):
        exact_binomial_interval(False, 5)


def test_cp_undefined_boundaries_return_none():
    assert exact_binomial_interval(0, 0) is None
    assert exact_binomial_interval(2, 1) is None
    assert exact_binomial_interval(-1, 10) is None
    assert exact_binomial_interval(11, 10) is None
    assert exact_binomial_interval(1, 1, confidence=1.0) is None
    assert exact_binomial_interval(1, 1, confidence=0.0) is None


# --- bootstrap --------------------------------------------------------------


def test_bootstrap_rejects_nonfinite_samples_before_small_n_return():
    with pytest.raises(ValueError, match="finite"):
        bootstrap_interval([float("nan"), 1.0])
    with pytest.raises(ValueError, match="finite"):
        bootstrap_interval([float("inf"), 2.0])
    with pytest.raises(ValueError, match="finite"):
        bootstrap_interval([float("-inf")])


def test_bootstrap_short_finite_samples_return_none():
    assert bootstrap_interval([1.0, 2.0]) is None
    values = [float(index) for index in range(20)]
    assert bootstrap_interval(values[:19]) is None


def test_bootstrap_rejects_invalid_configuration():
    values = [float(index) for index in range(20)]
    with pytest.raises(ValueError, match="statistic"):
        bootstrap_interval([1.0, 2.0], statistic="bogus")
    with pytest.raises(ValueError, match="confidence"):
        bootstrap_interval(values, confidence=1.5)
    with pytest.raises(ValueError, match="resamples"):
        bootstrap_interval(values, resamples=-5)
    with pytest.raises(ValueError, match="resamples"):
        bootstrap_interval(values, resamples=0)
    with pytest.raises(ValueError, match="seed"):
        bootstrap_interval(values, seed=True)
    with pytest.raises(ValueError, match="minimum_n"):
        bootstrap_interval(values, minimum_n=1)


def test_bootstrap_is_reproducible_and_seed_sensitive():
    values = [float(index * index % 23) for index in range(40)]
    assert bootstrap_interval(values, seed=7) == bootstrap_interval(values, seed=7)
    assert bootstrap_interval(values, seed=7) != bootstrap_interval(values, seed=8)


def test_bootstrap_mean_and_median_differ_on_skewed_sample():
    values = [1.0] * 15 + [2.0] * 4 + [100.0]
    mean_interval = bootstrap_interval(values, statistic="mean", resamples=500)
    median_interval = bootstrap_interval(values, statistic="median", resamples=500)
    assert mean_interval[1] > median_interval[1]


def test_bootstrap_constant_sample_collapses_to_the_constant():
    interval = bootstrap_interval([4.0] * 25, resamples=100)
    assert interval == (4.0, 4.0)


def test_bootstrap_honors_minimum_n_override():
    values = [1.0, 2.0, 3.0, 4.0]
    assert bootstrap_interval(values) is None
    assert bootstrap_interval(values, minimum_n=4) is not None
    assert bootstrap_interval(values[:3], minimum_n=4) is None


# --- numeric and ordinal summaries ------------------------------------------


def test_numeric_summary_keeps_pinned_quartiles_and_flags_nothing_new():
    values = [float(index) for index in range(20)]
    summary = numeric_summary(values)
    assert summary["n"] == 20
    assert summary["quartiles"] == {"q1": 4.75, "q3": 14.25}
    assert summary["bootstrap_mean_interval"] is not None
    assert numeric_summary([]) == {"n": 0, "missing": True}
    assert numeric_summary(values, bootstrap=False)["bootstrap_mean_interval"] is None
    assert numeric_summary(values[:10])["bootstrap_mean_interval"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_numeric_summary_rejects_nonfinite_values(value):
    with pytest.raises(ValueError, match="finite"):
        numeric_summary([value])
    with pytest.raises(ValueError, match="finite"):
        numeric_summary([1.0, value])


def test_ordinal_summary_reports_distribution_and_mode():
    summary = ordinal_summary([0, 1, 1, 3, 4, 4, 4])
    assert summary["n"] == 7
    assert summary["distribution"] == {
        "0": 1,
        "1": 2,
        "2": 0,
        "3": 1,
        "4": 3,
    }
    assert summary["mode"] == [4]
    assert summary["mode_share"] == pytest.approx(3 / 7)


def test_ordinal_summary_multimodal_and_empty():
    assert ordinal_summary([1, 1, 3, 3])["mode"] == [1, 3]
    assert ordinal_summary([]) == {
        "n": 0,
        "missing": True,
        "distribution": {},
        "mode": [],
        "mode_share": None,
    }


def test_ordinal_summary_rejects_non_integer_out_of_scale_and_bad_scale():
    with pytest.raises(ValueError, match="integers"):
        ordinal_summary([1.5])
    with pytest.raises(ValueError, match="integers"):
        ordinal_summary([True])
    with pytest.raises(ValueError, match="integers"):
        ordinal_summary([5])
    with pytest.raises(ValueError, match="scale"):
        ordinal_summary([1], minimum=4, maximum=4)
    assert ordinal_summary([2, 3], minimum=2, maximum=3)["mode"] == [2, 3]


# --- weighted kappa ----------------------------------------------------------


def test_kappa_hand_computed_values():
    # Unweighted-equivalent binary case: po=3/4, pe=1/2 -> kappa=1/2.
    assert weighted_cohen_kappa(
        {"a": 0, "b": 0, "c": 1, "d": 1},
        {"a": 0, "b": 0, "c": 0, "d": 1},
        minimum=0,
        maximum=1,
    ) == pytest.approx(0.5)
    # Three-category linear weights: po=5/6, pe=11/18 -> kappa=4/7.
    assert weighted_cohen_kappa(
        {"a": 0, "b": 1, "c": 2},
        {"a": 1, "b": 1, "c": 2},
        minimum=0,
        maximum=2,
    ) == pytest.approx(4 / 7)


def test_kappa_perfect_agreement_and_degenerate_marginals():
    assert weighted_cohen_kappa({"a": 1, "b": 2}, {"a": 1, "b": 2}) == 1.0
    assert weighted_cohen_kappa({}, {}) is None
    assert weighted_cohen_kappa({"case": 4}, {"case": 4}) is None
    # One constant rater against a varying one: po == pe, so kappa is 0,
    # not undefined; undefined is reserved for expected agreement equal 1.
    assert weighted_cohen_kappa({"a": 4, "b": 4}, {"a": 4, "b": 3}) == 0.0


def test_kappa_rejects_invalid_scale_and_type_violations():
    with pytest.raises(ValueError, match="scale"):
        weighted_cohen_kappa({"a": 1}, {"a": 1}, minimum=4, maximum=4)
    with pytest.raises(ValueError, match="scale"):
        weighted_cohen_kappa({"a": 1}, {"a": 1}, minimum=1, maximum=0)
    with pytest.raises(ValueError, match="integers within"):
        weighted_cohen_kappa({"a": 5}, {"a": 1})
    with pytest.raises(ValueError, match="integers within"):
        weighted_cohen_kappa({"a": True}, {"a": 1})
    with pytest.raises(ValueError, match="integers within"):
        weighted_cohen_kappa({"a": 1.5}, {"a": 1})


# --- review summary -----------------------------------------------------------


def test_review_summary_reports_ordinal_distribution_per_criterion():
    rating = ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3)
    second = ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3)
    summary = review_summary((rating, second))
    assert summary["status"] == "complete"
    coverage = summary["criteria"]["semantic_coverage"]
    assert coverage["distribution"] == {"0": 0, "1": 0, "2": 0, "3": 0, "4": 2}
    assert coverage["mode"] == [4]
    assert coverage["bootstrap_mean_interval"] is None
    # Both raters scored semantic_coverage, verification_quality,
    # provenance_fidelity, and readability identically, so kappa is
    # undefined there; procedural_usefulness and safety vary.
    assert set(summary["agreement_undefined"]) == {
        "semantic_coverage",
        "verification_quality",
        "provenance_fidelity",
        "readability",
    }
    for criterion in ("procedural_usefulness", "safety"):
        assert isinstance(summary["agreement"][criterion], float)


def test_review_summary_lists_undefined_agreement_criterion():
    rating = ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3)
    second = ReviewRating("case", "r2", 4, 2, 2, 4, 4, 3)
    summary = review_summary((rating, second))
    assert "safety" in summary["agreement_undefined"]
    assert summary["agreement"]["safety"] is None


def test_review_summary_pending_single_rater_still_reports_distribution():
    rating = ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3)
    summary = review_summary((rating,))
    assert summary["status"] == "pending"
    assert summary["agreement"] == {}
    assert summary["criteria"]["readability"]["distribution"]["3"] == 1


def test_review_summary_rejects_duplicate_rows():
    rating = ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3)
    with pytest.raises(ValueError, match="unique"):
        review_summary((rating, rating))


# --- report policy metadata and integrity -------------------------------------


def test_summarize_observations_embeds_policy_and_small_sample_flags():
    summary = summarize_observations((_observation(),))
    assert summary["policy"] == policy_payload()
    assert summary["small_sample_metrics"] == [
        "generation_duration_ms",
        "page_count",
        "request_count",
        "response_bytes",
    ]
    assert summary["proportions"]["package_valid"]["exact_95_interval"] is not None


def test_summarize_observations_missing_fallback_excluded_from_denominator():
    missing = _observation(metadata={"missing_metrics": ["fallback_used"]})
    summary = summarize_observations((missing,))
    assert summary["fallback_rate"] is None
    assert summary["proportions"]["fallback_used"]["total"] == 0


def test_report_round_trip(tmp_path):
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3, notes="checked"),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3, notes="checked"),
    )
    report = build_evaluation_report((_observation(),), ratings=ratings)
    destination = write_evaluation_report(report, tmp_path)
    loaded = load_evaluation_report(destination)
    assert loaded.ratings == ratings
    assert loaded.summary["review"]["status"] == "complete"
    assert loaded.summary["policy"] == policy_payload()
    assert loaded.summary["review"]["criteria"]["safety"]["distribution"] == {
        "0": 0,
        "1": 0,
        "2": 0,
        "3": 1,
        "4": 1,
    }


def test_self_consistent_forgery_without_rows_is_rejected(tmp_path):
    """A rehashed payload must still fail the row-presence semantic gate."""
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload["summary"]["review"]["rating_count"] = 2
    payload["summary"]["review"]["status"] = "complete"
    payload["summary"]["review"]["agreement"] = {"safety": 0.9}
    payload.pop("artifact_sha256")
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "self-consistent.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="without rating rows"):
        load_evaluation_report(path)


def test_self_consistent_forgery_with_rows_is_rejected(tmp_path):
    """A rehashed payload must still fail the review-recomputation gate."""
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3, notes="checked"),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3, notes="checked"),
    )
    report = build_evaluation_report((_observation(),), ratings=ratings)
    payload = report.to_dict()
    payload["summary"]["review"]["rating_count"] = 5
    payload.pop("artifact_sha256")
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "self-consistent.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="disagrees with rating rows"):
        load_evaluation_report(path)


def test_legacy_pending_report_without_ratings_still_loads(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("ratings", None)  # simulate a pre-ratings report payload
    payload.pop("artifact_sha256")
    # Also simulate the pre-policy summary shape by dropping the new keys.
    payload["summary"].pop("policy", None)
    payload["summary"].pop("small_sample_metrics", None)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_evaluation_report(path)
    assert loaded.ratings == ()
    assert loaded.summary["review"]["status"] == "pending"
    assert loaded.summary["review"]["rating_count"] == 0
    # Missing legacy keys are reconstructed from the observations, not
    # silently defaulted, and the digest is rederived over the merge.
    assert loaded.summary["policy"] == policy_payload()
    assert loaded.summary["observation_count"] == 1
    assert loaded.summary["review"]["criteria"]
    expected_digest = sha256_json(
        {
            key: value
            for key, value in loaded.to_dict().items()
            if key != "artifact_sha256"
        }
    )
    assert loaded.artifact_sha256 == expected_digest


def test_rating_status_envelope_must_match_rederived_review_status(tmp_path):
    ratings = (
        ReviewRating("case", "r1", 4, 3, 2, 4, 4, 3, notes="checked"),
        ReviewRating("case", "r2", 4, 2, 2, 4, 3, 3, notes="checked"),
    )
    report = build_evaluation_report((_observation(),), ratings=ratings)
    payload = report.to_dict()
    payload.pop("artifact_sha256")
    payload["rating_status"] = "pending"  # forged envelope: rows say complete
    path = tmp_path / "status-mismatch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="rating_status disagrees"):
        load_evaluation_report(path)


def test_rating_status_complete_without_rows_or_review_is_rejected(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("artifact_sha256")
    payload["rating_status"] = "complete"
    payload["summary"].pop("review", None)
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "envelope-forgery.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="without rating rows"):
        load_evaluation_report(path)


def test_legacy_partial_review_is_reconstructed_not_fabricated(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("ratings", None)
    payload.pop("artifact_sha256")
    payload["summary"]["review"] = {"rating_count": 0}
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "sparse-review.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_evaluation_report(path)
    review = loaded.summary["review"]
    assert review["rating_count"] == 0
    assert review["status"] == "pending"
    assert review["criteria"]


def test_current_report_rejects_missing_summary_keys(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("artifact_sha256")
    payload["summary"] = {"review": payload["summary"]["review"]}
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "sparse-summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="missing keys"):
        load_evaluation_report(path)


def test_current_report_rejects_missing_review_keys(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("artifact_sha256")
    payload["summary"]["review"] = {"rating_count": 0}
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "sparse-current-review.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="review summary is missing keys"):
        load_evaluation_report(path)


def test_current_report_rejects_absent_review_summary(tmp_path):
    report = build_evaluation_report((_observation(),))
    payload = report.to_dict()
    payload.pop("artifact_sha256")
    payload["summary"].pop("review", None)
    payload["artifact_sha256"] = sha256_json(payload)
    path = tmp_path / "absent-review.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="require a review summary"):
        load_evaluation_report(path)


# --- large-n exact-interval oracles -----------------------------------------


def _binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    log_pmf = (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
    )
    return math.exp(log_pmf)


def _binom_leq(k: int, n: int, p: float) -> float:
    """P(X <= k) with complement sums; never from an underflowed start."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    k = min(k, n)
    if k >= (n + 1) * p:
        return 1.0 - _binom_geq(k + 1, n, p)
    term = _binom_pmf(k, n, p)
    total = term
    for j in range(k, 0, -1):
        term = term * j / (n - j + 1) * ((1.0 - p) / p)
        total += term
    return min(1.0, total)


def _binom_geq(k: int, n: int, p: float) -> float:
    """P(X >= k) with complement sums; never from an underflowed start."""
    if k <= 0:
        return 1.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    if k > n:
        return 0.0
    if k <= (n + 1) * p:
        return 1.0 - _binom_leq(k - 1, n, p)
    term = _binom_pmf(k, n, p)
    total = term
    for j in range(k, n):
        term = term * (n - j) / (j + 1) * (p / (1.0 - p))
        total += term
    return min(1.0, total)


@pytest.mark.parametrize(
    ("successes", "total"),
    [(500, 1000), (5000, 10000), (50000, 100000), (1, 100000), (99999, 100000)],
)
def test_cp_large_n_endpoints_satisfy_defining_tail_equations(
    successes: int, total: int
) -> None:
    lower, upper = exact_binomial_interval(successes, total)
    # Defining property (Clopper & Pearson 1934): each endpoint solves an
    # exact binomial tail equation at alpha/2, evaluated here by stable
    # exact tail sums that never start from an underflowing term.
    assert _binom_geq(successes, total, lower) == pytest.approx(0.025, abs=1e-9)
    assert _binom_leq(successes, total, upper) == pytest.approx(0.025, abs=1e-9)
    assert lower < successes / total < upper


@pytest.mark.parametrize("confidence", [0.90, 0.99])
def test_cp_nondefault_confidence_satisfies_tail_equations(
    confidence: float,
) -> None:
    successes, total = 3, 10000
    lower, upper = exact_binomial_interval(successes, total, confidence)
    alpha_tail = (1.0 - confidence) / 2.0
    assert _binom_geq(successes, total, lower) == pytest.approx(alpha_tail, abs=1e-9)
    assert _binom_leq(successes, total, upper) == pytest.approx(alpha_tail, abs=1e-9)


# --- additional kappa and bootstrap oracles ----------------------------------


def test_kappa_antisymmetric_and_shift_oracles():
    # Both raters uniform over 0..2, perfectly anti-correlated pairs:
    # po = 1/3, pe = 5/9, so kappa = -1/2.
    assert weighted_cohen_kappa(
        {"a": 0, "b": 1, "c": 2},
        {"a": 2, "b": 1, "c": 0},
        minimum=0,
        maximum=2,
    ) == pytest.approx(-0.5)
    # Five one-step-shifted pairs on a 0..4 scale: po = pe = 0.6 exactly.
    assert weighted_cohen_kappa(
        {str(index): index for index in range(5)},
        {str(index): (index + 1) % 5 for index in range(5)},
    ) == pytest.approx(0.0, abs=1e-12)


def test_bootstrap_extreme_resample_counts_clamp_indices():
    values = [float(index % 7) for index in range(25)]
    low, high = bootstrap_interval(values, resamples=1)
    assert low == high
    assert 0.0 <= low <= 6.0


def test_policy_confidence_nan_is_rejected():
    with pytest.raises(ValueError, match="confidence"):
        validate_policy(StatisticalPolicy(confidence=float("nan")))
