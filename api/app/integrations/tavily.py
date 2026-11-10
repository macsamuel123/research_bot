"""Tavily adapter for SearchClient (plain httpx)."""

from __future__ import annotations

from typing import Any

import httpx

from app.integrations.search import SearchClient, SearchError, SearchResult

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TIMEOUT_SECONDS = 20.0


class TavilySearch:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def __repr__(self) -> str:
        return "TavilySearch()"

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    TAVILY_SEARCH_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"query": query, "max_results": max_results, "search_depth": "basic"},
                )
        except httpx.HTTPError as exc:
            raise SearchError(f"Tavily request failed: {type(exc).__name__}") from None
        if not resp.is_success:
            raise SearchError(f"Tavily HTTP {resp.status_code}")
        try:
            body: Any = resp.json()
        except ValueError:
            raise SearchError("Tavily returned invalid JSON") from None
        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            raise SearchError("Tavily response has no results list")
        out: list[SearchResult] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url, title, content = item.get("url"), item.get("title"), item.get("content")
            if isinstance(url, str) and url:
                out.append(
                    SearchResult(
                        title=title if isinstance(title, str) else "",
                        url=url,
                        content=content if isinstance(content, str) else "",
                    )
                )
        return out


_conforms: type[SearchClient] = TavilySearch
