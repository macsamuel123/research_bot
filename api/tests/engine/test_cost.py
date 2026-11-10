from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.engine import cost
from app.engine.cost import Prices, compute

pytestmark = pytest.mark.criterion("M8-C9")

DEFAULT = Prices(input_cents_per_mtok=300, output_cents_per_mtok=1500, search_cents_per_1k=800)
ENGINE = Path(cost.__file__).parent


@pytest.mark.parametrize(
    ("inp", "out", "searches", "expected"),
    [
        (0, 0, 0, 0),
        (1, 0, 0, 1),  # 300 / 1e6 cents rounds up to 1
        (1_000_000, 0, 0, 300),
        (0, 1_000_000, 0, 1500),
        (0, 0, 1, 1),  # 0.8 cents -> 1
        (0, 0, 5, 4),
        (0, 0, 1000, 800),
        (10_000, 2_000, 2, 8),  # 3_000_000 + 3_000_000 + 1_600_000 -> 7.6 -> 8
    ],
)
def test_compute_known_values(inp: int, out: int, searches: int, expected: int) -> None:
    assert compute(inp, out, searches, DEFAULT) == expected


_n = st.integers(min_value=0, max_value=10**9)
_p = st.integers(min_value=1, max_value=100_000)


@given(_n, _n, st.integers(0, 10**6), _p, _p, _p, st.integers(0, 10**6), st.sampled_from([0, 1, 2]))
def test_compute_int_nonneg_monotonic(
    inp: int, out: int, s: int, pi: int, po: int, ps: int, delta: int, which: int
) -> None:
    prices = Prices(pi, po, ps)
    base = compute(inp, out, s, prices)
    assert type(base) is int and base >= 0
    bumped = [inp, out, s]
    bumped[which] += delta
    more = compute(bumped[0], bumped[1], bumped[2], prices)
    assert type(more) is int and more >= base


def _tokens(path: Path) -> list[tokenize.TokenInfo]:
    return list(tokenize.generate_tokens(io.StringIO(path.read_text()).readline))


def test_cost_and_budget_source_have_no_float_decimal_or_true_division() -> None:
    for name in ("cost.py", "budget.py"):
        toks = _tokens(ENGINE / name)
        names = {t.string for t in toks if t.type == tokenize.NAME}
        ops = [t.string for t in toks if t.type == tokenize.OP]
        assert "float" not in names and "Decimal" not in names, name
        assert "/" not in ops and "/=" not in ops, name
        if name == "cost.py":
            assert ops.count("//") == 1
            assert not any(
                t.type == tokenize.NUMBER and ("." in t.string or "e" in t.string.lower())
                for t in toks
            )
