"""RunBudget: the only path from the engine to LLMClient and SearchClient (INV-9).

M8 does accounting only (usage, call counts, spent cents). M10 adds the caps and the
projection checks here. Integer arithmetic only (INV-1).
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator

from app.config import Settings
from app.engine import cost
from app.integrations.llm import LLMClient, LLMEvent, LLMRequest, LLMResponse
from app.integrations.search import SearchClient, SearchResult

SEARCH_MAX_RESULTS = 5


class RunBudget:
    def __init__(self, llm: LLMClient, search: SearchClient, settings: Settings) -> None:
        self._llm = llm
        self._search = search
        self._settings = settings
        self._prices = cost.Prices.from_settings(settings)
        self.llm_calls = 0
        self.search_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def spent_cents(self) -> int:
        return cost.compute(self.input_tokens, self.output_tokens, self.search_calls, self._prices)

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream one LLM call; always sends max_tokens=LLM_MAX_TOKENS and records usage."""
        request = dataclasses.replace(request, max_tokens=self._settings.llm_max_tokens)
        self.llm_calls += 1
        async for event in self._llm.stream(request):
            if isinstance(event, LLMResponse):
                self.input_tokens += event.usage.input_tokens
                self.output_tokens += event.usage.output_tokens
            yield event

    async def search(self, query: str) -> list[SearchResult]:
        self.search_calls += 1
        return await self._search.search(query, max_results=SEARCH_MAX_RESULTS)
