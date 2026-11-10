from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.routers.health import DbCheck, db_check

pytestmark = pytest.mark.criterion("M1-C2")


def test_health_ok_with_db(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


def test_health_degraded_when_db_check_raises(client: TestClient) -> None:
    def failing() -> DbCheck:
        def check() -> None:
            raise RuntimeError("db down")

        return check

    client.app.dependency_overrides[db_check] = failing  # type: ignore[attr-defined]
    try:
        resp = client.get("/health")
    finally:
        client.app.dependency_overrides.clear()  # type: ignore[attr-defined]
    assert resp.status_code == 503
    assert resp.json() == {"status": "degraded", "db": "error"}


def test_default_docs_disabled(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert client.get(path).status_code == 404
