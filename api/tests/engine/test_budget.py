from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.engine.budget import RunBudget
from app.engine.cost import Prices, compute
from app.integrations.fakes import FakeLLM, FakeSearch, FakeTurn
from app.integrations.llm import LLMRequest, Usage

pytestmark = pytest.mark.criterion("M8-C8")


def test_budget_forces_max_tokens_and_sums_usage(settings: Settings) -> None:
    llm = FakeLLM([FakeTurn(usage=Usage(10, 3)), FakeTurn(usage=Usage(7, 5))])
    search = FakeSearch()
    budget = RunBudget(llm, search, settings)

    async def go() -> None:
        for _ in range(2):
            async for _event in budget.stream(LLMRequest(system="", messages=[], max_tokens=1)):
                pass
        await budget.search("q")

    asyncio.run(go())
    assert [r.max_tokens for r in llm.requests] == [settings.llm_max_tokens] * 2
    assert (budget.llm_calls, budget.input_tokens, budget.output_tokens) == (2, 17, 8)
    assert budget.search_calls == search.call_count == 1
    assert search.calls[0][1] == 5
    assert budget.spent_cents == compute(17, 8, 1, Prices.from_settings(settings))
