from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.auth.client_ip import client_ip
from app.auth.password import hash_password
from app.auth.session import COOKIE_NAME, make_token, verify_token
from app.clock import FakeClock
from app.config import Settings, load_settings
from app.main import create_app

PASSWORD = "correct horse battery"
WRONG = "nope"


@pytest.fixture
def login_client(
    settings: Settings, clean_env: pytest.MonkeyPatch, clock: FakeClock
) -> Iterator[TestClient]:
    clean_env.setenv("OWNER_PASSWORD_HASH", hash_password(PASSWORD))
    clean_env.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    with TestClient(create_app(load_settings(), clock=clock)) as c:
        yield c


def test_login_sets_httponly_lax_cookie_and_unlocks_routes(login_client: TestClient) -> None:
    assert login_client.get("/api/auth/me").status_code == 401
    resp = login_client.post("/api/auth/login", json={"password": PASSWORD})
    assert resp.status_code == 204
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Secure" not in cookie  # PUBLIC_BASE_URL is http in tests
    assert login_client.get("/api/auth/me").json() == {"owner": True}
    assert login_client.post("/api/auth/logout").status_code == 204
    assert login_client.get("/api/auth/me").status_code == 401


def test_wrong_password_is_401(login_client: TestClient) -> None:
    resp = login_client.post("/api/auth/login", json={"password": "nope"})
    assert resp.status_code == 401
    assert "set-cookie" not in resp.headers


def test_login_is_rate_limited(login_client: TestClient, clock: FakeClock) -> None:
    def attempt(password: str = WRONG) -> int:
        return login_client.post("/api/auth/login", json={"password": password}).status_code

    assert [attempt() for _ in range(5)] == [401] * 5
    assert attempt() == 429
    assert attempt(PASSWORD) == 429  # even the right password is refused while limited
    clock.advance(timedelta(seconds=61))
    assert attempt(PASSWORD) == 204


def _request(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_client_ip_trusts_xff_only_from_trusted_proxy(
    clean_env: pytest.MonkeyPatch, settings: Settings
) -> None:
    clean_env.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")
    trusted = load_settings()
    assert client_ip(_request("127.0.0.1", "1.1.1.1, 10.0.0.9"), trusted) == "10.0.0.9"
    assert client_ip(_request("127.0.0.1"), trusted) == "127.0.0.1"
    assert client_ip(_request("10.1.1.1", "10.0.0.9"), trusted) == "10.1.1.1"
    assert client_ip(_request("127.0.0.1", "10.0.0.9"), settings) == "127.0.0.1"


def test_session_token_expires_and_is_tamper_proof(clock: FakeClock) -> None:
    token = make_token("s3cret", clock.now(), 1)
    assert verify_token("s3cret", token, clock.now())
    assert not verify_token("other", token, clock.now())
    assert not verify_token("s3cret", token.replace(".", ".0", 1), clock.now())
    assert not verify_token("s3cret", "garbage", clock.now())
    assert not verify_token("s3cret", token, clock.now() + timedelta(days=1, seconds=1))
