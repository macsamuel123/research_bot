"""INV-2 / INV-10: findings and runs are inserted only by their owning service."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"


def _patterns(model: str) -> list[re.Pattern[str]]:
    return [re.compile(rf"\b{model}\("), re.compile(rf"\b(?:pg_)?insert\(\s*{model}\b")]


OWNERS = {"Finding": "services/findings.py", "Run": "services/runs.py"}


def _offenders(model: str) -> list[str]:
    hits = []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        if rel == OWNERS[model] or rel.startswith("models/"):
            continue
        text = path.read_text()
        if any(p.search(text) for p in _patterns(model)):
            hits.append(rel)
    return hits


@pytest.mark.criterion("M8-C5")
def test_findings_inserted_only_by_save_finding() -> None:
    assert _offenders("Finding") == []


@pytest.mark.criterion("M8-C1")
def test_runs_created_only_by_open_run() -> None:
    assert _offenders("Run") == []


def test_patterns_are_word_bounded() -> None:
    for model, near_miss in (("Run", "DigestRun("), ("Finding", "TestFinding(")):
        assert not any(p.search(near_miss) for p in _patterns(model))
        assert any(p.search(f"x = {model}(a=1)") for p in _patterns(model))
        assert any(p.search(f"pg_insert({model})") for p in _patterns(model))
