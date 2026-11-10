"""Tavily adapter for SearchClient. Implemented in M8."""

from __future__ import annotations

from app.integrations.search import SearchClient, SearchResult


class TavilySearch:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def __repr__(self) -> str:
        return "TavilySearch()"

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        raise NotImplementedError("TavilySearch.search is implemented in M8")


_conforms: type[SearchClient] = TavilySearch
