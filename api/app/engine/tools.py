"""Tool schemas the agent offers to the model."""

from __future__ import annotations

from typing import Any

WEB_SEARCH = "web_search"
SAVE_FINDING = "save_finding"

TOOLS: list[dict[str, Any]] = [
    {
        "name": WEB_SEARCH,
        "description": (
            "Search the web. Returns up to 5 results with title, url and content. "
            "Only URLs returned by this tool may be saved as findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    {
        "name": SAVE_FINDING,
        "description": (
            "Save one cited finding. The url must be one that web_search returned in this run. "
            "Duplicates of already-saved findings are skipped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title of the finding"},
                "url": {"type": "string", "description": "Source URL from web_search"},
                "summary": {"type": "string", "description": "One or two sentence summary"},
            },
            "required": ["title", "url", "summary"],
        },
    },
]
