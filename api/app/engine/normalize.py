"""URL and text normalization used for finding validation and dedupe (M8-C6)."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS: frozenset[str] = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "ref"})

_WS = re.compile(r"\s+")


class InvalidUrl(ValueError):  # noqa: N818 - domain name, not an "Error" suffix
    """The string cannot be parsed as a URL (bad port, unbalanced IPv6 brackets, ...)."""


def _is_tracking(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in TRACKING_PARAMS


def normalize_url(url: str) -> str:
    """Canonical form of `url`. Idempotent: normalize_url(normalize_url(u)) == normalize_url(u).

    - lowercases the scheme and the netloc (host and port)
    - drops the fragment
    - drops `utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid` and `ref` (case-insensitive keys)
    - sorts the remaining query params by (key, value)
    - turns an empty path into `/` when there is a host
    """
    try:
        parts = urlsplit(url.strip())
        _ = parts.port  # raises ValueError on a bad port
    except ValueError as exc:
        raise InvalidUrl("unparseable url") from exc
    pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True, errors="replace")
        if not _is_tracking(k)
    ]
    pairs.sort()
    path = parts.path
    if not path and parts.netloc:
        path = "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(pairs), ""))


def normalize_text(value: str) -> str:
    """NFKC, lowercase, collapse whitespace, strip."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", value).lower()).strip()
