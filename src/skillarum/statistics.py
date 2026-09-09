"""Dependency-light statistics and the canonical Skillarum statistical policy.

Every inferential number the evaluation layer publishes about itself is
computed here from the Python standard library alone, so reports stay
auditable without scipy or numpy.

Conventions
-----------
- A statistic that is genuinely undefined for the data at hand returns
  ``None``: an empty or below-floor sample, a proportion without a usable
  denominator, a boundary confidence level, or chance-corrected agreement
  whose expected value is 1 (identical constant marginals).
- Invalid usage raises ``ValueError``: non-integer or boolean binomial
  counts, non-finite samples, an unknown bootstrap statistic, an
  inconsistent ordinal scale, or a non-positive resampling configuration.
  Input validity is checked before any small-sample early return, so a
  non-finite sample is never silently reported as "too small to estimate".
- All randomness flows through one seeded Mersenne Twister per call, so
  intervals are byte-identical across runs for the same inputs and policy.

The canonical parameter choices live in ``StatisticalPolicy`` and
``DEFAULT_POLICY``; reports embed them via :func:`policy_payload` and the
manuscript layer auto-injects them from there.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, fields
from statistics import fmean, median, stdev
from typing import Any, Literal

from .utils import jsonable

__all__ = [
    "DEFAULT_POLICY",
    "POLICY_BOOTSTRAP_METHOD",
    "POLICY_INTERVAL_METHOD",
    "StatisticalPolicy",
    "bootstrap_interval",
    "exact_binomial_interval",
    "numeric_summary",
    "ordinal_summary",
    "policy_from_mapping",
    "policy_payload",
    "validate_policy",
    "weighted_cohen_kappa",
]

POLICY_INTERVAL_METHOD = "clopper_pearson_exact"
POLICY_BOOTSTRAP_METHOD = "percentile"


@dataclass(frozen=True)
class StatisticalPolicy:
    """Validated canonical choices for inferential reporting.

    ``confidence``: two-sided confidence level for exact and bootstrap
    intervals. ``bootstrap_minimum_n``: smallest sample size that earns a
    bootstrap interval; below it the interval is reported as ``None``.
    ``bootstrap_seed`` / ``bootstrap_resamples``: reproducible percentile
    bootstrap configuration. ``rating_minimum`` / ``rating_maximum``:
    inclusive bounds of the ordinal rating scale (must satisfy
    ``0 <= rating_minimum < rating_maximum``).
    """

    confidence: float = 0.95
    bootstrap_minimum_n: int = 20
    bootstrap_seed: int = 1729
    bootstrap_resamples: int = 2000
    rating_minimum: int = 0
    rating_maximum: int = 4


DEFAULT_POLICY = StatisticalPolicy()


def _is_plain_int(value: Any) -> bool:
    """True for real integers; bools are counts-in-waiting, not counts."""
    return type(value) is int


def validate_policy(policy: StatisticalPolicy) -> StatisticalPolicy:
    """Reject a policy that would silently produce misleading statistics."""
    if not _is_plain_int(policy.bootstrap_seed):
        raise ValueError(
            f"policy bootstrap_seed must be an integer, got {policy.bootstrap_seed!r}"
        )
    if not _is_plain_int(policy.bootstrap_minimum_n) or policy.bootstrap_minimum_n < 2:
        raise ValueError(
            "policy bootstrap_minimum_n must be an integer of at least 2, "
            f"got {policy.bootstrap_minimum_n!r}"
        )
    if not _is_plain_int(policy.bootstrap_resamples) or policy.bootstrap_resamples < 1:
        raise ValueError(
            "policy bootstrap_resamples must be a positive integer, "
            f"got {policy.bootstrap_resamples!r}"
        )
    if not 0.0 < policy.confidence < 1.0:
        raise ValueError(
            f"policy confidence must lie strictly between 0 and 1, "
            f"got {policy.confidence!r}"
        )
    if (
        not _is_plain_int(policy.rating_minimum)
        or not _is_plain_int(policy.rating_maximum)
        or not 0 <= policy.rating_minimum < policy.rating_maximum
    ):
        raise ValueError(
            "policy rating scale must satisfy 0 <= rating_minimum < "
            f"rating_maximum, got ({policy.rating_minimum!r}, "
            f"{policy.rating_maximum!r})"
        )
    return policy


def policy_payload(policy: StatisticalPolicy = DEFAULT_POLICY) -> dict[str, Any]:
    """JSON-safe description of the policy actually used to compute a report."""
    validate_policy(policy)
    return {
        "confidence": policy.confidence,
        "bootstrap_minimum_n": policy.bootstrap_minimum_n,
        "bootstrap_seed": policy.bootstrap_seed,
        "bootstrap_resamples": policy.bootstrap_resamples,
        "rating_minimum": policy.rating_minimum,
        "rating_maximum": policy.rating_maximum,
        "interval_method": POLICY_INTERVAL_METHOD,
        "bootstrap_method": POLICY_BOOTSTRAP_METHOD,
    }


def policy_from_mapping(value: Any) -> StatisticalPolicy:
    """Build a policy from a partial mapping; unknown keys are rejected."""
    if value is None:
        return DEFAULT_POLICY
    if not isinstance(value, dict):
        raise ValueError(f"policy mapping must be a dict, got {type(value)!r}")
    known = {item.name for item in fields(StatisticalPolicy)}
    unknown = sorted(set(value) - known)
    if unknown:
        raise ValueError(f"unknown statistical policy fields: {unknown}")
    supplied = {name: value[name] for name in known if name in value}
    return validate_policy(StatisticalPolicy(**supplied))


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    max_iterations = 200
    epsilon = 3.0e-14
    tiny = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for iteration in range(1, max_iterations + 1):
        m2 = 2 * iteration
        aa = iteration * (b - iteration) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + iteration) * (qab + iteration) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return h


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(
        a * math.log(x)
        + b * math.log1p(-x)
        - math.lgamma(a)
        - math.lgamma(b)
        + math.lgamma(a + b)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_inverse(probability: float, a: float, b: float) -> float:
    if probability <= 0:
        return 0.0
    if probability >= 1:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(80):
        middle = (low + high) / 2.0
        if _regularized_beta(middle, a, b) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def exact_binomial_interval(
    successes: int, total: int, confidence: float = DEFAULT_POLICY.confidence
) -> tuple[float, float] | None:
    """Return a Clopper–Pearson interval for a binomial proportion.

    Following Clopper & Pearson (1934), the lower limit solves
    ``P(X >= successes | p) = (1 - confidence) / 2`` and the upper limit
    solves ``P(X <= successes | p) = (1 - confidence) / 2``.

    Returns ``None`` for an empty denominator, an out-of-range count, or a
    boundary confidence level; raises ``ValueError`` for non-integer or
    boolean counts, which are caller bugs rather than data conditions.
    """
    if not _is_plain_int(successes) or not _is_plain_int(total):
        raise ValueError(
            f"binomial counts must be integers, got ({successes!r}, {total!r})"
        )
    if total <= 0 or not 0 <= successes <= total or not 0 < confidence < 1:
        return None
    alpha = 1.0 - confidence
    lower = (
        0.0
        if successes == 0
        else _beta_inverse(alpha / 2.0, successes, total - successes + 1)
    )
    upper = (
        1.0
        if successes == total
        else _beta_inverse(1.0 - alpha / 2.0, successes + 1, total - successes)
    )
    return (lower, upper)


def bootstrap_interval(
    values: list[float],
    *,
    statistic: Literal["mean", "median"] = "mean",
    confidence: float = DEFAULT_POLICY.confidence,
    seed: int = DEFAULT_POLICY.bootstrap_seed,
    resamples: int = DEFAULT_POLICY.bootstrap_resamples,
    minimum_n: int = DEFAULT_POLICY.bootstrap_minimum_n,
) -> tuple[float, float] | None:
    """Return a reproducible percentile bootstrap interval (Efron, 1979).

    Returns ``None`` when the sample has fewer than ``minimum_n`` finite
    values — a data condition, not an error. Raises ``ValueError`` for
    non-finite values or an invalid configuration. Validity checks run
    before the small-sample early return.

    Endpoints are the order statistics of the resample distribution at
    ``int(tail * B)`` and ``int((1 - tail) * B) - 1``, clamped into range,
    where ``tail = (1 - confidence) / 2`` and ``B = resamples``. Percentile
    intervals are approximate; no finite-sample coverage calibration is
    claimed or implied.
    """
    if statistic not in {"mean", "median"}:
        raise ValueError("statistic must be mean or median")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    if not _is_plain_int(seed):
        raise ValueError(f"seed must be an integer, got {seed!r}")
    if not _is_plain_int(resamples) or resamples <= 0:
        raise ValueError(f"resamples must be a positive integer, got {resamples!r}")
    if not _is_plain_int(minimum_n) or minimum_n < 2:
        raise ValueError(
            f"minimum_n must be an integer of at least 2, got {minimum_n!r}"
        )
    if any(not math.isfinite(value) for value in values):
        raise ValueError("numeric values must be finite")
    if len(values) < minimum_n:
        return None
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(resamples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(fmean(sample) if statistic == "mean" else median(sample))
    estimates.sort()
    tail = (1.0 - confidence) / 2.0
    low_index = max(0, min(len(estimates) - 1, int(tail * len(estimates))))
    high_index = max(0, min(len(estimates) - 1, int((1.0 - tail) * len(estimates)) - 1))
    return estimates[low_index], estimates[high_index]


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def numeric_summary(
    values: list[float],
    *,
    seed: int = DEFAULT_POLICY.bootstrap_seed,
    bootstrap: bool = True,
) -> dict[str, Any]:
    """Describe a numeric sample without overstating small-sample precision.

    Applies to numerical measurements and counts alike — a mean is
    meaningful for both. For descriptive rubric-score averages callers disable
    bootstrap and also report :func:`ordinal_summary`. Below the policy bootstrap floor the interval
    is ``None``; callers that need to flag small samples should compare
    ``n`` against ``DEFAULT_POLICY.bootstrap_minimum_n``.
    """
    if any(not math.isfinite(value) for value in values):
        raise ValueError("numeric values must be finite")
    if not values:
        return {"n": 0, "missing": True}
    result: dict[str, Any] = {
        "n": len(values),
        "missing": False,
        "min": min(values),
        "max": max(values),
        "mean": fmean(values),
        "median": median(values),
        "quartiles": {"q1": _quantile(values, 0.25), "q3": _quantile(values, 0.75)},
        "stdev": stdev(values) if len(values) > 1 else None,
        "bootstrap_mean_interval": bootstrap_interval(values, seed=seed)
        if bootstrap
        else None,
    }
    return jsonable(result)


def ordinal_summary(
    values: list[int],
    *,
    minimum: int = DEFAULT_POLICY.rating_minimum,
    maximum: int = DEFAULT_POLICY.rating_maximum,
) -> dict[str, Any]:
    """Summarize an ordinal rating sample as an empirical distribution.

    The distribution, mode, and modal share are reported alongside the
    moments that callers may still compute; medians are equally valid
    ordinal summaries, and means are interpretable only as averages of
    rubric scores. The distribution is keyed by stringified category so
    payloads stay JSON-safe.
    """
    if not _is_plain_int(minimum) or not _is_plain_int(maximum) or maximum <= minimum:
        raise ValueError(
            "ordinal scale must satisfy minimum < maximum as integers, "
            f"got ({minimum!r}, {maximum!r})"
        )
    for value in values:
        if not _is_plain_int(value) or not minimum <= value <= maximum:
            raise ValueError(
                f"ordinal values must be integers in [{minimum}, {maximum}], "
                f"got {value!r}"
            )
    if not values:
        return {
            "n": 0,
            "missing": True,
            "distribution": {},
            "mode": [],
            "mode_share": None,
        }
    counts = {category: 0 for category in range(minimum, maximum + 1)}
    for value in values:
        counts[value] += 1
    top = max(counts.values())
    mode = sorted(category for category, count in counts.items() if count == top)
    return {
        "n": len(values),
        "missing": False,
        "distribution": {
            str(category): counts[category] for category in sorted(counts)
        },
        "mode": mode,
        "mode_share": top / len(values),
    }


def weighted_cohen_kappa(
    first: dict[str, int],
    second: dict[str, int],
    *,
    minimum: int = DEFAULT_POLICY.rating_minimum,
    maximum: int = DEFAULT_POLICY.rating_maximum,
) -> float | None:
    """Compute linearly weighted Cohen's kappa for paired ordinal ratings.

    Following Cohen (1968) with linear weights, disagreements one category
    apart earn partial credit. Returns ``None`` only when no case is rated
    by both raters or when the expected weighted agreement is 1 (both
    raters' marginals identical and concentrated on one category), where
    chance-corrected agreement is undefined; one constant rater against a
    varying one yields kappa 0, not ``None``. Raises ``ValueError`` for an
    inconsistent scale or ratings outside it.
    """
    if not _is_plain_int(minimum) or not _is_plain_int(maximum) or maximum <= minimum:
        raise ValueError(
            "kappa scale must satisfy minimum < maximum as integers, "
            f"got ({minimum!r}, {maximum!r})"
        )
    keys = sorted(set(first).intersection(second))
    if not keys:
        return None
    if any(
        not _is_plain_int(score) or not minimum <= score <= maximum
        for ratings in (first, second)
        for score in ratings.values()
    ):
        raise ValueError("kappa ratings must be integers within the declared scale")
    categories = list(range(minimum, maximum + 1))
    observed = 0.0
    expected = 0.0
    n = len(keys)
    for left in categories:
        for right in categories:
            weight = 1.0 - abs(left - right) / (maximum - minimum)
            observed += (
                weight
                * sum(1 for key in keys if first[key] == left and second[key] == right)
                / n
            )
            expected += (
                weight
                * (sum(1 for key in keys if first[key] == left) / n)
                * (sum(1 for key in keys if second[key] == right) / n)
            )
    if math.isclose(expected, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return None  # expected agreement is 1: identical constant marginals
    return (observed - expected) / (1.0 - expected)
