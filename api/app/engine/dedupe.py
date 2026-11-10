"""Finding hashes. Uniqueness itself is enforced by the DB (INV-3)."""

from __future__ import annotations

import hashlib

from app.engine.normalize import normalize_text


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def url_hash(normalized_url: str) -> str:
    return _sha(normalized_url)


def content_hash(title: str, summary: str) -> str:
    return _sha(normalize_text(title) + "\n" + normalize_text(summary))


def dedupe_hash(url_hash_value: str, content_hash_value: str) -> str:
    return _sha(url_hash_value + content_hash_value)
