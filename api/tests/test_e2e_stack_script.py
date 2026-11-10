from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import pytest

from app.config import subprocess_env

API_PORT = 8001
WEB_PORT = 3001


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.criterion("M1-C8")
@pytest.mark.enable_socket
def test_stack_script_stops_processes_on_failure(
    repo_root: Path, tmp_path: Path, test_db_url: str
) -> None:
    assert not _port_open(API_PORT) and not _port_open(WEB_PORT), "ports busy before test"
    marker = tmp_path / "ran"
    probe = (
        f"curl -fsS http://127.0.0.1:{API_PORT}/health > {tmp_path}/health.json"
        f" && touch {marker} && exit 7"
    )
    result = subprocess.run(
        ["./scripts/e2e-stack.sh"],
        cwd=repo_root,
        env=subprocess_env(TEST_DATABASE_URL=test_db_url, E2E_STACK_CMD=probe),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 7, result.stdout + result.stderr
    assert marker.exists()
    assert '"db":"ok"' in (tmp_path / "health.json").read_text()
    assert not _port_open(API_PORT)
    assert not _port_open(WEB_PORT)
