"""Auth dependencies, attached at router level (INV-4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.auth.session import COOKIE_NAME, verify_token
from app.clock import Clock, get_clock
from app.config import Settings

#: The only routes reachable without credentials. Changing this must be called out in the PR.
PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/api/auth/login"})


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_owner(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if not verify_token(settings.session_secret, token, clock.now()):
        raise HTTPException(status_code=401, detail="Not authenticated")
