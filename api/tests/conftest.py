from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.auth.session import COOKIE_NAME, make_token
from app.clock import FakeClock
from app.config import (
    NON_SETTINGS_ENV,
    Settings,
    get_settings,
    load_settings,
    read_test_database_url,
)
from app.main import create_app
from app.testdb import ensure_database

pytest_plugins = ["tests.helpers.engine"]

# Distinctive dummy secrets so redaction/leak tests can search for them.
DUMMY_SECRETS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "sk-ant-dummy-AAAA1111",
    "TAVILY_API_KEY": "tvly-dummy-BBBB2222",
    "TELEGRAM_BOT_TOKEN": "123456:dummy-CCCC3333",
    "OWNER_PASSWORD_HASH": "$argon2id$v=19$m=65536,t=3,p=4$dummyDDDD4444",
    "SESSION_SECRET": "session-dummy-EEEE5555",
}
DUMMY_DB_PASSWORD = "dbpass-dummy-FFFF6666"


def make_valid_env(**overrides: str) -> dict[str, str]:
    env = {
        **DUMMY_SECRETS,
        "ANTHROPIC_MODEL": "claude-sonnet-5-5",
        "DATABASE_URL": f"postgresql+psycopg://research:{DUMMY_DB_PASSWORD}@db.invalid:5432/rb",
        "OWNER_CHAT_ID": "42",
        "PUBLIC_BASE_URL": "http://127.0.0.1:3000",
        "RUN_BUDGET_CENTS": "50",
        "RUN_MAX_SEARCH_CALLS": "8",
    }
    env.update(overrides)
    return env


@pytest.fixture
def valid_env() -> dict[str, str]:
    return make_valid_env()


@pytest.fixture
def clean_env(
    monkeypatch: pytest.MonkeyPatch, valid_env: dict[str, str]
) -> Iterator[pytest.MonkeyPatch]:
    """Remove every Settings/NON_SETTINGS key from the env, then apply `valid_env`."""
    for name in {*(f.upper() for f in Settings.model_fields), *NON_SETTINGS_ENV}:
        monkeypatch.delenv(name, raising=False)
    for key, value in valid_env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = read_test_database_url()
    ensure_database(url)
    return url


@pytest.fixture
def settings(clean_env: pytest.MonkeyPatch, test_db_url: str) -> Settings:
    clean_env.setenv("DATABASE_URL", test_db_url)
    clean_env.setenv("INTEGRATIONS_MODE", "fake")
    clean_env.setenv("APP_ENV", "test")
    clean_env.setenv("WORKER_ENABLED", "false")
    return load_settings()


API_DIR = Path(__file__).resolve().parents[1]
TABLES = ("finding", "run", "message", "research", "api_key")


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture(scope="session")
def migrated_db(test_db_url: str) -> Iterator[Engine]:
    """Migrations run once per session."""
    command.upgrade(alembic_config(test_db_url), "head")
    engine = create_engine(test_db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(migrated_db: Engine) -> Engine:
    """All tables are truncated before each test that touches the DB."""
    with migrated_db.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    return migrated_db


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(settings: Settings, db_engine: Engine, clock: FakeClock) -> Iterator[TestClient]:
    """Anonymous client (no session cookie)."""
    with TestClient(create_app(settings, clock=clock)) as c:
        yield c


@pytest.fixture
def owner_client(settings: Settings, db_engine: Engine, clock: FakeClock) -> Iterator[TestClient]:
    """Client carrying a valid owner session cookie."""
    with TestClient(create_app(settings, clock=clock)) as c:
        c.cookies.set(COOKIE_NAME, make_token(settings.session_secret, clock.now(), 30))
        yield c


@pytest.fixture(scope="session")
def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    )
    return Path(out.stdout.strip())
