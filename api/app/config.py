"""Application settings. This is the ONLY module that reads the process environment."""

from __future__ import annotations

import ipaddress
import os
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

#: Keys that appear in `.env.example` but are not Settings fields.
NON_SETTINGS_ENV: frozenset[str] = frozenset(
    {
        "BIND_ADDR",
        "API_INTERNAL_URL",
        "NEXT_PUBLIC_USE_MOCKS",
        "TEST_DATABASE_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    }
)

#: Required env vars; startup fails if any is missing.
REQUIRED_ENV: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "TAVILY_API_KEY",
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "OWNER_CHAT_ID",
    "OWNER_PASSWORD_HASH",
    "SESSION_SECRET",
    "PUBLIC_BASE_URL",
    "RUN_BUDGET_CENTS",
    "RUN_MAX_SEARCH_CALLS",
)

#: Env vars that must be strictly positive integers.
POSITIVE_INT_ENV: tuple[str, ...] = (
    "RUN_BUDGET_CENTS",
    "RUN_MAX_SEARCH_CALLS",
    "RUN_MAX_LLM_CALLS",
    "LLM_MAX_TOKENS",
    "RUN_TIMEOUT_SECONDS",
    "PRICE_INPUT_CENTS_PER_MTOK",
    "PRICE_OUTPUT_CENTS_PER_MTOK",
    "PRICE_SEARCH_CENTS_PER_1K",
)

#: Settings fields whose values are secrets (the DB password is handled separately).
SECRET_FIELDS: tuple[str, ...] = (
    "anthropic_api_key",
    "tavily_api_key",
    "telegram_bot_token",
    "owner_password_hash",
    "session_secret",
)

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://research:research@127.0.0.1:5433/research_test"


class SettingsError(RuntimeError):
    """Raised when the environment does not produce valid Settings. Never contains values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # --- required ---
    anthropic_api_key: str
    anthropic_model: str
    tavily_api_key: str
    database_url: str
    telegram_bot_token: str
    owner_chat_id: int
    owner_password_hash: str
    session_secret: str
    public_base_url: str
    run_budget_cents: PositiveInt
    run_max_search_calls: PositiveInt

    # --- environment and integrations ---
    app_env: Literal["development", "test", "production"] = "development"
    integrations_mode: Literal["real", "fake"] = "real"
    fake_llm_chunk_delay_ms: NonNegativeInt = 0

    # --- worker ---
    worker_enabled: bool = True
    worker_tick_seconds: PositiveInt = 60

    # --- session and login ---
    session_max_age_days: PositiveInt = 30
    login_rate_limit_per_min: PositiveInt = 5
    trusted_proxy_cidrs: str = ""

    # --- run limits ---
    run_max_llm_calls: PositiveInt = 12
    llm_max_tokens: PositiveInt = 2048
    run_timeout_seconds: PositiveInt = 180
    run_stale_after_seconds: PositiveInt = 600

    # --- prices (integer cents) ---
    price_input_cents_per_mtok: PositiveInt = 300
    price_output_cents_per_mtok: PositiveInt = 1500
    price_search_cents_per_1k: PositiveInt = 800

    # --- digest ---
    digest_synth_reserve_cents: NonNegativeInt = 10
    digest_cache_hours: PositiveInt = 24

    @field_validator(
        "anthropic_api_key",
        "anthropic_model",
        "tavily_api_key",
        "database_url",
        "telegram_bot_token",
        "owner_password_hash",
        "session_secret",
    )
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("public_base_url")
    @classmethod
    def _absolute_http_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
        except ValueError:
            raise ValueError("must be an absolute http(s) URL") from None
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("must be an absolute http(s) URL with a host")
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def _valid_cidrs(cls, value: str) -> str:
        for item in _split_csv(value):
            try:
                ipaddress.ip_network(item, strict=False)
            except ValueError:
                raise ValueError("must be a comma list of CIDRs") from None
        return value

    @model_validator(mode="after")
    def _cross_field(self) -> Self:
        if self.run_stale_after_seconds <= self.run_timeout_seconds:
            raise ValueError("RUN_STALE_AFTER_SECONDS must be greater than RUN_TIMEOUT_SECONDS")
        if self.digest_synth_reserve_cents >= self.run_budget_cents:
            raise ValueError("DIGEST_SYNTH_RESERVE_CENTS must be less than RUN_BUDGET_CENTS")
        if self.integrations_mode == "fake" and self.app_env == "production":
            raise ValueError("INTEGRATIONS_MODE=fake is not allowed when APP_ENV=production")
        if self.app_env == "production" and urlsplit(self.public_base_url).scheme != "https":
            raise ValueError("PUBLIC_BASE_URL must be https:// when APP_ENV=production")
        return self

    @property
    def trusted_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [ipaddress.ip_network(c, strict=False) for c in _split_csv(self.trusted_proxy_cidrs)]

    @property
    def public_base_is_https(self) -> bool:
        return urlsplit(self.public_base_url).scheme == "https"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _format_validation_error(exc: ValidationError) -> str:
    """Build a message from locations and messages only — never input values or ctx."""
    lines = []
    for err in exc.errors(include_input=False, include_context=False, include_url=False):
        loc = err.get("loc", ())
        name = ".".join(str(part) for part in loc).upper() if loc else "settings"
        lines.append(f"{name}: {err.get('msg', 'invalid')}")
    return "Invalid configuration:\n  " + "\n  ".join(lines)


def load_settings() -> Settings:
    """Load Settings from the environment, raising SettingsError that names the variables."""
    try:
        return Settings()  # values come from env
    except ValidationError as exc:
        message = _format_validation_error(exc)
    raise SettingsError(message) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def secret_values(settings: Settings) -> list[str]:
    """Every secret value that must never be logged, longest first."""
    values = [str(getattr(settings, name)) for name in SECRET_FIELDS]
    try:
        db_password = make_url(settings.database_url).password
    except Exception:  # noqa: BLE001 - unparsable URL simply has no extractable password
        db_password = None
    if db_password:
        values.append(str(db_password))
    return sorted({v for v in values if v}, key=len, reverse=True)


def read_test_database_url() -> str:
    """The test DB URL (tests must not read env themselves)."""
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def subprocess_env(drop: frozenset[str] | set[str] = frozenset(), **extra: str) -> dict[str, str]:
    """A copy of the process env for spawning tools (tests/scripts), minus `drop`, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(extra)
    return env
