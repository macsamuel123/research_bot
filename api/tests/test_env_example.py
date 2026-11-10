from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.config import NON_SETTINGS_ENV, Settings

pytestmark = pytest.mark.criterion("M1-C4")

SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "TAVILY_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "OWNER_PASSWORD_HASH",
    "SESSION_SECRET",
    "POSTGRES_PASSWORD",
)


def _example(repo_root: Path) -> str:
    return (repo_root / ".env.example").read_text()


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = stripped.partition("=")
        assert sep, f"malformed line: {line!r}"
        assert key not in values, f"duplicate key {key}"
        values[key.strip()] = value.strip()
    return values


def test_env_example_keys_match_settings_plus_allowlist(repo_root: Path) -> None:
    assert NON_SETTINGS_ENV == {
        "BIND_ADDR",
        "API_INTERNAL_URL",
        "NEXT_PUBLIC_USE_MOCKS",
        "TEST_DATABASE_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    }
    keys = set(_parse(_example(repo_root)))
    expected = {name.upper() for name in Settings.model_fields} | NON_SETTINGS_ENV
    assert keys == expected


def test_secret_values_are_placeholders(repo_root: Path) -> None:
    values = _parse(_example(repo_root))
    for key in SECRET_KEYS:
        assert values[key].startswith("replace-me"), key
    db_password = make_url(values["DATABASE_URL"]).password
    assert db_password is not None and db_password.startswith("replace-me")
    # The only non-placeholder credential is the documented local test DB default.
    assert values["TEST_DATABASE_URL"].endswith("@127.0.0.1:5433/research_test")


def test_anthropic_model_has_verify_comment(repo_root: Path) -> None:
    lines = _example(repo_root).splitlines()
    idx = next(i for i, line in enumerate(lines) if line.startswith("ANTHROPIC_MODEL="))
    assert lines[idx] == "ANTHROPIC_MODEL=claude-sonnet-5-5"
    context = "\n".join(lines[max(0, idx - 2) : idx + 1]).lower()
    assert "verify before deploy" in context


def test_env_example_documents_tailscale_and_dollar_escaping(repo_root: Path) -> None:
    text = _example(repo_root)
    comments = "\n".join(line for line in text.splitlines() if line.lstrip().startswith("#"))
    assert "tailscale serve" in comments
    assert "MagicDNS" in comments
    assert re.search(r"https://\S+\.ts\.net", comments)
    assert "$$" in comments
    assert "OWNER_PASSWORD_HASH" in text
    lines = text.splitlines()
    idx = next(i for i, line in enumerate(lines) if line.startswith("OWNER_PASSWORD_HASH="))
    assert "$$" in "\n".join(lines[max(0, idx - 4) : idx])
