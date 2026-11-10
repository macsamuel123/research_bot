"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.rate_limit import RateLimiter
from app.clock import Clock, SystemClock
from app.config import Settings, load_settings
from app.db import make_engine
from app.errors import DomainError
from app.integrations.factory import get_integrations
from app.logging import setup_logging
from app.routers import auth, findings, health, researches


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    setup_logging(settings)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Research Bot",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        swagger_ui_oauth2_redirect_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.integrations = get_integrations(settings)
    app.state.clock = clock if clock is not None else SystemClock()
    app.state.login_limiter = RateLimiter(settings.login_rate_limit_per_min)

    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(health.router)
    app.include_router(auth.public_router)
    app.include_router(auth.router)
    app.include_router(researches.router)
    app.include_router(findings.router)
    return app
