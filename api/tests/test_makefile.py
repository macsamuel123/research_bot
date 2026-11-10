from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.mark.criterion("M1-C1")
def test_make_test_invokes_all_targets(repo_root: Path) -> None:
    out = subprocess.run(
        ["make", "-n", "test"], cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout
    expected_in_order = [
        "==> test-api",
        "cd api && uv run pytest",
        "==> test-web",
        "cd web && pnpm test && pnpm test:e2e",
        "==> e2e-stack",
        "scripts/e2e-stack.sh",
    ]
    pos = -1
    for fragment in expected_in_order:
        found = out.find(fragment, pos + 1)
        assert found > pos, f"{fragment!r} missing or out of order in:\n{out}"
        pos = found
