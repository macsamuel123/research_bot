from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _ignored(repo_root: Path, path: str) -> int:
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path], cwd=repo_root, check=False
    ).returncode


@pytest.mark.criterion("M1-C5")
def test_env_files_ignored_example_not(repo_root: Path) -> None:
    assert _ignored(repo_root, ".env") == 0
    assert _ignored(repo_root, ".env.local") == 0
    assert _ignored(repo_root, ".env.example") == 1
