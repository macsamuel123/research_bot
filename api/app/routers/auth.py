"""POST /api/auth/login (public, rate-limited), POST /api/auth/logout, GET /api/auth/me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth.client_ip import client_ip
from app.auth.deps import get_app_settings, require_owner
from app.auth.password import verify_password
from app.auth.rate_limit import RateLimiter
from app.auth.session import COOKIE_NAME, make_token
from app.clock import Clock, get_clock
from app.config import Settings
from app.schemas.auth import LoginIn, MeOut

public_router = APIRouter(prefix="/api/auth", tags=["auth"])
router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(require_owner)])


def get_login_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.login_limiter
    return limiter


@public_router.post("/login", status_code=204)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    limiter: Annotated[RateLimiter, Depends(get_login_limiter)],
) -> None:
    now = clock.now()
    if not limiter.allow(client_ip(request, settings), now):
        raise HTTPException(status_code=429, detail="Too many login attempts")
    if not verify_password(settings.owner_password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    response.set_cookie(
        COOKIE_NAME,
        make_token(settings.session_secret, now, settings.session_max_age_days),
        max_age=settings.session_max_age_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_is_https,
        path="/",
    )


@router.post("/logout", status_code=204)
def logout(response: Response, settings: Annotated[Settings, Depends(get_app_settings)]) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_is_https,
        path="/",
    )


@router.get("/me")
def me() -> MeOut:
    return MeOut(owner=True)
