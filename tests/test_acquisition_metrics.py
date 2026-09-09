"""Run-manifest retry-budget metrics over real acquisition events."""

from __future__ import annotations

import json

from skillarum.models import CrawlConfig, ExtractionConfig, SourceProfile, TargetSpec
from skillarum.pipeline import acquisition_metrics, run_profile


def test_acquisition_metrics_counts_retries_and_timeouts() -> None:
    events = [
        {
            "kind": "page",
            "url": "http://127.0.0.1:1/page",
            "status": "retrying",
            "status_code": 503,
            "request_attempt": True,
        },
        {
            "kind": "page",
            "url": "http://127.0.0.1:1/page",
            "status": "received",
            "status_code": 200,
            "duration_ms": 42,
            "request_attempt": True,
        },
        {
            "kind": "page",
            "url": "http://127.0.0.1:1/page",
            "status": "rejected",
            "reason": "ReadTimeout",
            "request_attempt": True,
        },
        {
            "kind": "robots",
            "url": "http://127.0.0.1:1/robots.txt",
            "status": "received",
            "status_code": 200,
            "duration_ms": 900,
            "request_attempt": True,
        },
        {
            "kind": "selection",
            "url": "http://127.0.0.1:1/other",
            "status": "rejected",
            "reason": "unsafe or unsupported URL",
            "request_attempt": False,
        },
    ]
    metrics = acquisition_metrics(events)
    assert metrics["requests"] == 4
    assert metrics["retries"] == 1
    assert metrics["timeouts"] == 1
    domains = metrics["domains"]
    assert set(domains) == {"127.0.0.1"}
    histogram = domains["127.0.0.1"]
    assert histogram["count"] == 2
    assert histogram["min_ms"] == 42
    assert histogram["max_ms"] == 900
    assert histogram["buckets"]["lt_100ms"] == 1
    assert histogram["buckets"]["300_1000ms"] == 1


def test_acquisition_metrics_buckets_extreme_latencies() -> None:
    metrics = acquisition_metrics(
        [
            {
                "url": "http://a.test/x",
                "status": "received",
                "duration_ms": 50,
                "request_attempt": True,
            },
            {
                "url": "http://a.test/y",
                "status": "revalidated",
                "duration_ms": 150,
                "request_attempt": True,
            },
            {
                "url": "http://a.test/z",
                "status": "received",
                "duration_ms": 5_000,
                "request_attempt": True,
            },
        ]
    )
    buckets = metrics["domains"]["a.test"]["buckets"]
    assert buckets == {
        "lt_100ms": 1,
        "100_300ms": 1,
        "300_1000ms": 0,
        "1000_3000ms": 0,
        "gte_3000ms": 1,
    }
    assert metrics["domains"]["a.test"]["p95_ms"] == 5_000


def test_acquisition_metrics_empty_events() -> None:
    metrics = acquisition_metrics([])
    assert metrics == {"requests": 0, "retries": 0, "timeouts": 0, "domains": {}}


def test_pipeline_manifest_reports_retry_budget(fixture_server, tmp_path) -> None:
    profile = SourceProfile(
        id="metrics",
        name="Metrics Site",
        base_url=fixture_server,
        crawl=CrawlConfig(
            respect_robots=False,
            allow_private_hosts=True,
            max_response_bytes=100_000,
        ),
        extraction=ExtractionConfig(main_selector="main"),
        targets=(TargetSpec(id="flaky", name="Flaky", urls=("/transient",)),),
    )
    run_profile(profile, output_dir=tmp_path)
    manifest = json.loads(next((tmp_path / "runs").glob("*/manifest.json")).read_text())
    metrics = manifest["acquisition_metrics"]
    assert metrics["retries"] == 1  # the fixture's first /transient request 503s
    assert metrics["requests"] >= 2
    assert metrics["timeouts"] == 0
    host, histogram = next(iter(metrics["domains"].items()))
    assert histogram["count"] >= 2
    assert histogram["buckets"]["lt_100ms"] >= 1
