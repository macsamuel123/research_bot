"""Web search seam (Tavily in production)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str


@runtime_checkable
class SearchClient(Protocol):
    async def search(self, query: str, max_results: int) -> list[SearchResult]: ...
