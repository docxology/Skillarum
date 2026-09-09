from __future__ import annotations

from pathlib import Path

import pytest

from skillarum.config import load_profile, profile_from_mapping
from skillarum.models import TargetSpec
from skillarum.urls import (
    is_public_http_url,
    normalize_url,
    path_matches,
    resolve_url,
    same_origin,
)
from skillarum.utils import artifact_name


ROOT = Path(__file__).resolve().parents[1]


def test_example_profiles_load() -> None:
    math = load_profile(ROOT / "data/sources/math4wisdom.yaml")
    aii = load_profile(ROOT / "data/sources/active_inference_institute.yaml")
    assert math.area == "Math4Wisdom"
    assert aii.area == "Active-Inference-Institute"
    assert math.target("three-minds").name == "Three-Minds"
    assert len(aii.target("institute-overview").urls) == 8


def test_profile_validation_rejects_missing_targets() -> None:
    with pytest.raises(ValueError, match="targets"):
        profile_from_mapping({"id": "empty", "base_url": "https://example.org"})
    with pytest.raises(ValueError, match="profile.id"):
        profile_from_mapping(
            {
                "name": "missing id",
                "base_url": "https://example.org",
                "targets": [{"id": "t"}],
            }
        )
    with pytest.raises(ValueError, match="targets must be a list"):
        profile_from_mapping(
            {"id": "bad", "base_url": "https://example.org", "targets": {}}
        )


def test_profile_file_and_dns_safety_validation(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("- not-a-profile\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_profile(malformed)
    assert not is_public_http_url("ftp://example.org/resource")
    assert not is_public_http_url("http://localhost:8000")
    assert not is_public_http_url("http://does-not-exist.invalid", resolve_dns=True)
    assert path_matches("https://example.org/docs", ())


def test_profile_validation_rejects_duplicate_target_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        profile_from_mapping(
            {
                "id": "duplicate",
                "base_url": "https://example.org",
                "targets": [{"id": "same"}, {"id": "same"}],
            }
        )


def test_urls_normalize_and_match() -> None:
    assert normalize_url("HTTPS://Example.org/path?utm_source=x&keep=1#part") == (
        "https://example.org/path?keep=1"
    )
    assert (
        resolve_url("https://example.org/docs/", "../page")
        == "https://example.org/page"
    )
    assert same_origin("https://example.org", "https://example.org:443/page")
    assert not same_origin("https://example.org", "http://example.org/page")
    assert path_matches("https://example.org/docs/page", ("/docs/*",))
    assert is_public_http_url("https://example.org")
    assert not is_public_http_url("http://127.0.0.1:8000")
    assert is_public_http_url("http://127.0.0.1:8000", allow_private=True)
    assert artifact_name("Three Minds!") == "Three-Minds"
    with pytest.raises(ValueError, match="credentials"):
        normalize_url("https://user:password@example.org/private")
    with pytest.raises(ValueError, match="unsupported URL"):
        normalize_url("not-a-url")


def test_target_parsing_supports_aliases() -> None:
    target = TargetSpec.from_mapping(
        {
            "id": "docs",
            "start_urls": ["/"],
            "prefixes": ["/guide/"],
            "include": ["/docs/*"],
            "exclude": ["/docs/private/*"],
        }
    )
    assert target.urls == ("/",)
    assert target.include_prefixes == ("/guide/",)
    assert target.include_patterns == ("/docs/*",)
    assert target.exclude_patterns == ("/docs/private/*",)
    assert target.slug == "docs"


def test_profile_validation_rejects_slugified_target_collisions() -> None:
    with pytest.raises(ValueError, match="slugified"):
        profile_from_mapping(
            {
                "id": "slug-collision",
                "base_url": "https://example.org",
                "targets": [
                    {"id": "My Target", "name": "Alpha"},
                    {"id": "my-target", "name": "Beta"},
                ],
            }
        )


def test_mapped_ipv6_private_destinations_are_rejected() -> None:
    """Negative control for the IPv4-mapped IPv6 loopback bypass: on some
    supported CPython patch levels is_private misses the embedded IPv4
    host, so the classification must unwrap the mapping itself."""
    assert not is_public_http_url("http://[::ffff:127.0.0.1]/")
    assert not is_public_http_url("http://[::ffff:127.0.0.1]/", resolve_dns=True)
    assert not is_public_http_url("http://[::ffff:10.0.0.5]/", resolve_dns=True)
    assert not is_public_http_url("http://[::ffff:169.254.169.254]/", resolve_dns=True)
    assert is_public_http_url("http://[::ffff:8.8.8.8]/", resolve_dns=True)


def test_profile_validation_rejects_non_mapping_targets() -> None:
    with pytest.raises(ValueError, match="mapping"):
        profile_from_mapping(
            {"id": "bad", "base_url": "https://example.org", "targets": ["x"]}
        )
