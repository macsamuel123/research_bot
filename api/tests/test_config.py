from __future__ import annotations

import traceback

import pytest

from app.config import (
    POSITIVE_INT_ENV,
    REQUIRED_ENV,
    Settings,
    SettingsError,
    load_settings,
)
from tests.conftest import DUMMY_DB_PASSWORD, DUMMY_SECRETS

pytestmark = pytest.mark.criterion("M1-C3")

# Literal lists from CLAUDE.md "Settings" and the M1 milestone text.
CLAUDE_MD_REQUIRED = {
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
}
MILESTONE_POSITIVE_INTS = {
    "RUN_BUDGET_CENTS",
    "RUN_MAX_SEARCH_CALLS",
    "RUN_MAX_LLM_CALLS",
    "LLM_MAX_TOKENS",
    "RUN_TIMEOUT_SECONDS",
    "PRICE_INPUT_CENTS_PER_MTOK",
    "PRICE_OUTPUT_CENTS_PER_MTOK",
    "PRICE_SEARCH_CENTS_PER_1K",
}


def _error(monkeypatch: pytest.MonkeyPatch, **env: str) -> SettingsError:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SettingsError) as info:
        load_settings()
    return info.value


def test_constants_match_documented_lists() -> None:
    assert set(REQUIRED_ENV) == CLAUDE_MD_REQUIRED
    assert set(POSITIVE_INT_ENV) == MILESTONE_POSITIVE_INTS
    fields = {f.upper() for f in Settings.model_fields}
    assert CLAUDE_MD_REQUIRED <= fields
    assert MILESTONE_POSITIVE_INTS <= fields
    required_fields = {n.upper() for n, f in Settings.model_fields.items() if f.is_required()}
    assert required_fields == CLAUDE_MD_REQUIRED


def test_valid_env_loads(clean_env: pytest.MonkeyPatch) -> None:
    s = load_settings()
    assert s.owner_chat_id == 42
    assert s.public_base_url == "http://127.0.0.1:3000"  # http is fine outside production
    assert s.app_env == "development"
    assert s.integrations_mode == "real"
    assert s.run_stale_after_seconds == 600
    assert s.run_timeout_seconds == 180
    assert s.digest_synth_reserve_cents == 10
    assert s.price_input_cents_per_mtok == 300
    assert isinstance(s.price_input_cents_per_mtok, int)


@pytest.mark.parametrize("name", REQUIRED_ENV)
def test_missing_required_var_fails_naming_it(clean_env: pytest.MonkeyPatch, name: str) -> None:
    clean_env.delenv(name)
    err = _error(clean_env)
    assert name in str(err)


@pytest.mark.parametrize("value", ["0", "-1", "0.5", "abc"])
@pytest.mark.parametrize("name", POSITIVE_INT_ENV)
def test_positive_int_settings_reject_bad_values(
    clean_env: pytest.MonkeyPatch, name: str, value: str
) -> None:
    # Keep cross-field rules satisfiable so only the bad value can fail.
    clean_env.setenv("DIGEST_SYNTH_RESERVE_CENTS", "0")
    err = _error(clean_env, **{name: value})
    assert name in str(err)


@pytest.mark.parametrize(("stale", "timeout"), [("180", "180"), ("100", "180")])
def test_stale_must_exceed_timeout(clean_env: pytest.MonkeyPatch, stale: str, timeout: str) -> None:
    err = _error(clean_env, RUN_STALE_AFTER_SECONDS=stale, RUN_TIMEOUT_SECONDS=timeout)
    assert "RUN_STALE_AFTER_SECONDS" in str(err)
    assert "RUN_TIMEOUT_SECONDS" in str(err)


@pytest.mark.parametrize("reserve", ["50", "60"])
def test_digest_reserve_below_budget(clean_env: pytest.MonkeyPatch, reserve: str) -> None:
    err = _error(clean_env, DIGEST_SYNTH_RESERVE_CENTS=reserve, RUN_BUDGET_CENTS="50")
    assert "DIGEST_SYNTH_RESERVE_CENTS" in str(err)


def test_fake_mode_refused_in_production(clean_env: pytest.MonkeyPatch) -> None:
    err = _error(
        clean_env,
        INTEGRATIONS_MODE="fake",
        APP_ENV="production",
        PUBLIC_BASE_URL="https://research.example.ts.net",
    )
    assert "INTEGRATIONS_MODE" in str(err)
    assert "APP_ENV" in str(err)


def test_fake_mode_allowed_in_test(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("INTEGRATIONS_MODE", "fake")
    clean_env.setenv("APP_ENV", "test")
    assert load_settings().integrations_mode == "fake"


@pytest.mark.parametrize("url", ["ftp://x", "/relative", "http://", "not a url", "https:///path"])
def test_public_base_url_invalid(clean_env: pytest.MonkeyPatch, url: str) -> None:
    err = _error(clean_env, PUBLIC_BASE_URL=url)
    assert "PUBLIC_BASE_URL" in str(err)


def test_production_requires_https(clean_env: pytest.MonkeyPatch) -> None:
    err = _error(clean_env, APP_ENV="production", PUBLIC_BASE_URL="http://100.64.0.1:3000")
    assert "PUBLIC_BASE_URL" in str(err)
    clean_env.setenv("PUBLIC_BASE_URL", "https://research.example.ts.net")
    assert load_settings().public_base_is_https


def test_settings_error_never_leaks_secrets(clean_env: pytest.MonkeyPatch) -> None:
    secrets = [*DUMMY_SECRETS.values(), DUMMY_DB_PASSWORD]
    # Field-level error plus a secret-looking invalid value; and a cross-field error.
    errors = [
        _error(clean_env, RUN_BUDGET_CENTS=DUMMY_SECRETS["SESSION_SECRET"]),
    ]
    clean_env.setenv("RUN_BUDGET_CENTS", "50")
    errors.append(_error(clean_env, RUN_STALE_AFTER_SECONDS="1"))
    for err in errors:
        rendered = [str(err), repr(err), "".join(traceback.format_exception(err))]
        for text in rendered:
            for secret in secrets:
                assert secret not in text
        assert err.__cause__ is None
        assert err.__suppress_context__ is True
