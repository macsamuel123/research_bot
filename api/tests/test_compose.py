from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.config import subprocess_env

pytestmark = pytest.mark.criterion("M1-C9")

# Simulate a fresh clone: none of the interpolated vars set in the environment.
_DROP = frozenset({"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "BIND_ADDR"})


def _compose(
    repo_root: Path, *files: str, json_out: bool = False
) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose"]
    for f in files:
        cmd += ["-f", f]
    cmd.append("config")
    if json_out:
        cmd += ["--format", "json"]
    return subprocess.run(
        cmd, cwd=repo_root, capture_output=True, text=True, env=subprocess_env(drop=_DROP)
    )


def _config(repo_root: Path, *files: str) -> dict[str, Any]:
    plain = _compose(repo_root, *files)
    assert plain.returncode == 0, plain.stderr
    out = _compose(repo_root, *files, json_out=True)
    assert out.returncode == 0, out.stderr
    data: dict[str, Any] = json.loads(out.stdout)
    return data


def test_compose_prod_config_valid_and_postgres_unpublished(repo_root: Path) -> None:
    services = _config(repo_root, "compose.yaml")["services"]
    assert {"postgres", "api", "web"} <= set(services)
    assert not services["postgres"].get("ports")
    assert not services["api"].get("ports")
    published = [name for name, svc in services.items() if svc.get("ports")]
    assert published == ["web"]
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert services["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"

    command = " ".join(services["api"]["command"])
    assert "alembic upgrade head &&" in command
    assert command.index("alembic upgrade head") < command.index("uvicorn")


def test_dev_overlay_publishes_postgres_on_loopback_5433(repo_root: Path) -> None:
    services = _config(repo_root, "compose.yaml", "compose.dev.yaml")["services"]
    ports = services["postgres"]["ports"]
    assert len(ports) == 1
    port = ports[0]
    assert port["host_ip"] == "127.0.0.1"
    assert str(port["published"]) == "5433"
    assert port["target"] == 5432
    assert not services["api"].get("ports")


def test_no_compose_override_tracked(repo_root: Path) -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    names = {Path(p).name for p in tracked}
    assert not names & {
        "compose.override.yaml",
        "compose.override.yml",
        "docker-compose.override.yaml",
        "docker-compose.override.yml",
    }
