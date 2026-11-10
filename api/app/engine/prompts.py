"""Prompt text for the research agent."""

from __future__ import annotations

from collections.abc import Sequence

MAX_STORED_URLS = 200


def build_system(topic: str, stored_urls: Sequence[str]) -> str:
    """System prompt. `stored_urls` are the research's saved finding URLs, newest first."""
    lines = [
        "You are a research assistant. Research the topic below using the web_search tool,",
        "then save each genuinely useful, sourced result with the save_finding tool.",
        "Rules:",
        "- Only save URLs that web_search returned in this conversation turn.",
        "- Keep unsourced claims in your prose; never save them as findings.",
        "- Finish with a short plain-text summary of what you found.",
        "",
        f"Research topic: {topic}",
    ]
    urls = list(stored_urls)[:MAX_STORED_URLS]
    if urls:
        lines += ["", "Already saved findings (do not save these again):"]
        lines += [f"- {u}" for u in urls]
    return "\n".join(lines)


def synthetic_prompt(topic: str) -> str:
    """User turn for runs without a user message (watch, digest)."""
    return f"Look for new developments on this topic and save any new findings: {topic}"
