from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from app.config import Settings
from app.integrations.search import SearchError, SearchResult
from app.integrations.tavily import TAVILY_SEARCH_URL, TavilySearch

pytestmark = pytest.mark.criterion("M8-C10")


def test_sends_configured_key_and_maps_results(settings: Settings) -> None:
    tavily = TavilySearch(api_key=settings.tavily_api_key)
    payload = {
        "query": "fusion",
        "results": [
            {"title": "A", "url": "https://a.example.com/x", "content": "aa", "score": 0.9},
            {"title": "B", "url": "https://b.example.com/y", "content": "bb", "score": 0.5},
            {"title": "no url"},
        ],
    }
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(TAVILY_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
        results = asyncio.run(tavily.search("fusion", max_results=5))
    sent = route.calls.last.request
    assert sent.headers["authorization"] == f"Bearer {settings.tavily_api_key}"
    assert json.loads(sent.content) == {
        "query": "fusion",
        "max_results": 5,
        "search_depth": "basic",
    }
    assert results == [
        SearchResult("A", "https://a.example.com/x", "aa"),
        SearchResult("B", "https://b.example.com/y", "bb"),
    ]


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_error_does_not_leak_key(settings: Settings, status: int) -> None:
    key = settings.tavily_api_key
    tavily = TavilySearch(api_key=key)
    with respx.mock as mock:
        mock.post(TAVILY_SEARCH_URL).mock(
            return_value=httpx.Response(status, json={"detail": f"bad key {key}"})
        )
        with pytest.raises(SearchError) as info:
            asyncio.run(tavily.search("q", max_results=5))
    assert key not in str(info.value) and str(status) in str(info.value)
    assert key not in repr(tavily)
