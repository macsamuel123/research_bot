"""INV-4 route coverage: every /api route outside PUBLIC_PATHS and /api/v1 depends on
require_owner, and answers 401 without a session before any 404/422."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.params import Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import BaseRoute

from app.auth.deps import PUBLIC_PATHS, require_owner


def _depends_on(dependant: Dependant, target: object) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def _routes(routes: Sequence[BaseRoute], inherited: bool) -> Iterator[tuple[APIRoute, bool]]:
    """(route, protected) pairs. Router-level dependencies count as protection."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route, inherited or _depends_on(route.dependant, require_owner)
            continue
        router: Any = getattr(route, "original_router", None)
        if router is not None:
            deps: list[Depends] = list(router.dependencies)
            protected = inherited or any(d.dependency is require_owner for d in deps)
            yield from _routes(router.routes, protected)


def _api_routes(client: TestClient) -> list[tuple[APIRoute, bool]]:
    app: Any = client.app
    return [(r, p) for r, p in _routes(app.routes, False) if r.path.startswith("/api/")]


def test_public_paths_are_exactly_health_and_login() -> None:
    assert frozenset({"/health", "/api/auth/login"}) == PUBLIC_PATHS


def test_every_owner_route_requires_owner(client: TestClient) -> None:
    routes = _api_routes(client)
    paths = {r.path for r, _ in routes}
    assert {"/api/researches/{research_id}", "/api/findings/{finding_id}/dismiss"} <= paths
    for route, protected in routes:
        if route.path in PUBLIC_PATHS or route.path.startswith("/api/v1/"):
            continue
        assert protected, route.path


def test_every_owner_route_answers_401_without_a_session(client: TestClient) -> None:
    app: Any = client.app
    spec = app.openapi()["paths"]
    assert spec
    for path, operations in spec.items():
        if path in PUBLIC_PATHS or not path.startswith("/api/"):
            continue
        concrete = path.replace("{research_id}", "999999").replace("{finding_id}", "999999")
        for method in operations:
            resp = client.request(method.upper(), concrete, json={"bogus": True})
            assert resp.status_code == 401, (method, path, resp.status_code)
