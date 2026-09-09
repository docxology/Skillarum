"""URL normalization and target matching."""

from __future__ import annotations

import fnmatch
import ipaddress
import socket
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Remove fragments and common tracking parameters while preserving content URLs."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported URL: {url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed")
    query_parts = [
        part
        for part in parsed.query.split("&")
        if part and not part.lower().split("=", 1)[0].startswith("utm_")
    ]
    path = parsed.path or "/"
    return urlunparse(
        ParseResult(
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            "&".join(query_parts),
            "",
        )
    )


def resolve_url(base_url: str, candidate: str) -> str:
    """Resolve a relative link and normalize it."""
    return normalize_url(urljoin(base_url, candidate))


def origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    return parsed.scheme.lower(), parsed.hostname or "", parsed.port


def same_origin(left: str, right: str) -> bool:
    """Return whether two URLs share scheme, hostname, and effective port."""
    left_scheme, left_host, left_port = origin(left)
    right_scheme, right_host, right_port = origin(right)
    default_left = left_port or (443 if left_scheme == "https" else 80)
    default_right = right_port or (443 if right_scheme == "https" else 80)
    return (left_scheme, left_host, default_left) == (
        right_scheme,
        right_host,
        default_right,
    )


def _forbidden_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Classify a resolved address, unwrapping IPv4-mapped IPv6 first.

    ``::ffff:127.0.0.1`` must be treated as loopback regardless of the
    running interpreter's ``ipaddress`` patch level: Python 3.10.0-3.10.13,
    3.11.0-3.11.8, and 3.12.0-3.12.3 classify mapped addresses as public
    because ``is_private``/``is_global`` miss the embedded IPv4 host.
    """
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def is_public_http_url(
    url: str, *, allow_private: bool = False, resolve_dns: bool = False
) -> bool:
    """Reject non-HTTP URLs and local/private destinations.

    The default remains a pure syntax check for offline callers.  Acquisition
    passes ``resolve_dns=True`` immediately before connecting so a hostname
    alias cannot bypass the literal-IP policy.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    if not allow_private and (
        host in {"localhost", "localhost.localdomain"} or host.endswith(".local")
    ):
        return False
    if allow_private:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not resolve_dns:
            return True
        try:
            addresses = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    host,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError):
            return False
        return bool(addresses) and not any(
            _forbidden_address(address) for address in addresses
        )
    return not _forbidden_address(address)


def path_matches(url: str, patterns: tuple[str, ...]) -> bool:
    """Match URL paths against shell-style patterns."""
    if not patterns:
        return True
    path = urlparse(url).path or "/"
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
