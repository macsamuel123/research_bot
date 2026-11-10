from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from app.config import Settings, load_settings
from app.logging import NOISY_LOGGERS, REDACTED, SecretRedactingFilter, setup_logging
from tests.conftest import DUMMY_DB_PASSWORD, DUMMY_SECRETS

pytestmark = pytest.mark.criterion("M1-C6")

SECRETS: dict[str, str] = {**DUMMY_SECRETS, "DATABASE_URL password": DUMMY_DB_PASSWORD}
LOGGER = "research_bot.test_logging"


@pytest.fixture
def loaded(clean_env: pytest.MonkeyPatch) -> Settings:
    return load_settings()


@pytest.fixture
def redacting_caplog(
    loaded: Settings, caplog: pytest.LogCaptureFixture
) -> Iterator[pytest.LogCaptureFixture]:
    setup_logging(loaded)
    flt = next(f for f in logging.getLogger().filters if isinstance(f, SecretRedactingFilter))
    caplog.handler.addFilter(flt)
    caplog.set_level(logging.INFO, logger=LOGGER)
    yield caplog
    caplog.handler.removeFilter(flt)


def _rendered(caplog: pytest.LogCaptureFixture) -> str:
    return caplog.text + "\n".join(r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("label", SECRETS)
def test_redacts_secrets_in_message(redacting_caplog: pytest.LogCaptureFixture, label: str) -> None:
    secret = SECRETS[label]
    logging.getLogger(LOGGER).info(f"value is {secret} here")
    text = _rendered(redacting_caplog)
    assert secret not in text
    assert f"value is {REDACTED} here" in text


@pytest.mark.parametrize("label", SECRETS)
def test_redacts_secrets_in_args(redacting_caplog: pytest.LogCaptureFixture, label: str) -> None:
    secret = SECRETS[label]
    logging.getLogger(LOGGER).info("token=%s count=%d", secret, 3)
    text = _rendered(redacting_caplog)
    assert secret not in text
    assert f"token={REDACTED} count=3" in text


@pytest.mark.parametrize("label", SECRETS)
def test_redacts_secrets_in_exception_text(
    redacting_caplog: pytest.LogCaptureFixture, label: str
) -> None:
    secret = SECRETS[label]
    try:
        raise RuntimeError(f"connect failed with {secret}")
    except RuntimeError:
        logging.getLogger(LOGGER).exception("boom")
    text = _rendered(redacting_caplog)
    assert "RuntimeError" in text
    assert f"connect failed with {REDACTED}" in text
    assert secret not in text


def test_database_url_password_is_a_secret(loaded: Settings) -> None:
    flt = SecretRedactingFilter([DUMMY_DB_PASSWORD])
    assert flt.redact(loaded.database_url) == loaded.database_url.replace(
        DUMMY_DB_PASSWORD, REDACTED
    )


def test_setup_logging_installs_filter_on_root_handlers(loaded: Settings) -> None:
    setup_logging(loaded)
    setup_logging(loaded)  # idempotent: no duplicate handlers/filters
    root = logging.getLogger()
    root_filters = [f for f in root.filters if isinstance(f, SecretRedactingFilter)]
    assert len(root_filters) == 1
    assert set(root_filters[0].secrets) == set(SECRETS.values())
    ours = [h for h in root.handlers if h.get_name() == "research-bot-root"]
    assert len(ours) == 1
    for handler in root.handlers:
        assert any(isinstance(f, SecretRedactingFilter) for f in handler.filters)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        assert any(isinstance(f, SecretRedactingFilter) for f in logging.getLogger(name).filters)


def test_noisy_loggers_at_warning(loaded: Settings) -> None:
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)
    setup_logging(loaded)
    assert set(NOISY_LOGGERS) == {"httpx", "httpcore", "telegram"}
    for name in NOISY_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


def test_uvicorn_access_records_stay_formattable_and_redacted() -> None:
    from uvicorn.logging import AccessFormatter

    flt = SecretRedactingFilter(["sekrit-token"])
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", "/api/x?key=sekrit-token", "1.1", 401),
        None,
    )
    assert flt.filter(record)
    line = AccessFormatter("%(message)s", use_colors=False).format(record)
    assert "sekrit-token" not in line
    assert '"GET /api/x?key=*** HTTP/1.1" 401' in line
