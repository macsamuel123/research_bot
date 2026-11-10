"""Stateless signed owner session: `<expiry epoch>.<hmac-sha256 hex>`."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta

COOKIE_NAME = "rb_session"


def _sign(secret: str, expires: int) -> str:
    return hmac.new(secret.encode(), f"owner:{expires}".encode(), hashlib.sha256).hexdigest()


def make_token(secret: str, now: datetime, max_age_days: int) -> str:
    expires = int((now + timedelta(days=max_age_days)).timestamp())
    return f"{expires}.{_sign(secret, expires)}"


def verify_token(secret: str, token: str | None, now: datetime) -> bool:
    if not token:
        return False
    expires_raw, sep, signature = token.partition(".")
    if not sep or not expires_raw.isdigit():
        return False
    expires = int(expires_raw)
    if not hmac.compare_digest(_sign(secret, expires), signature):
        return False
    return expires > int(now.timestamp())
