from __future__ import annotations

import asyncio
import socket

import pytest
from pytest_socket import SocketBlockedError

from app.config import Settings, load_settings
from app.integrations.anthropic_llm import AnthropicLLM
from app.integrations.factory import get_integrations
from app.integrations.fakes import FakeLLM, FakeNotifier, FakeSearch, FakeTurn
from app.integrations.llm import LLMClient, LLMRequest, LLMResponse, TextDelta, ToolUse, Usage
from app.integrations.notifier import Alert, Notifier
from app.integrations.search import SearchClient
from app.integrations.tavily import TavilySearch
from app.integrations.telegram_notifier import TelegramNotifier

pytestmark = pytest.mark.criterion("M1-C7")


def test_network_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("api.anthropic.com", 443))
    with pytest.raises(SocketBlockedError):
        socket.create_connection(("api.anthropic.com", 443), timeout=2)


def test_fakes_satisfy_protocols() -> None:
    assert isinstance(FakeLLM(), LLMClient)
    assert isinstance(FakeSearch(), SearchClient)
    assert isinstance(FakeNotifier(), Notifier)


def test_fake_mode_returns_fakes(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("INTEGRATIONS_MODE", "fake")
    clean_env.setenv("APP_ENV", "test")
    explicit = get_integrations(load_settings())
    implicit = get_integrations()  # falls back to get_settings() (env)
    for integ in (explicit, implicit):
        assert isinstance(integ.llm, FakeLLM)
        assert isinstance(integ.search, FakeSearch)
        assert isinstance(integ.notifier, FakeNotifier)


def test_fake_mode_refused_in_production(clean_env: pytest.MonkeyPatch) -> None:
    s = load_settings().model_copy(update={"integrations_mode": "fake", "app_env": "production"})
    with pytest.raises(RuntimeError, match="production"):
        get_integrations(s)


def test_real_mode_returns_real_adapters(clean_env: pytest.MonkeyPatch) -> None:
    s: Settings = load_settings()
    integ = get_integrations(s)
    assert isinstance(integ.llm, AnthropicLLM)
    assert isinstance(integ.search, TavilySearch)
    assert isinstance(integ.notifier, TelegramNotifier)
    assert s.anthropic_api_key not in repr(integ)


def test_fake_llm_streams_script_and_records_request() -> None:
    tool = ToolUse(id="t1", name="web_search", input={"query": "x"})
    llm = FakeLLM(
        [
            FakeTurn(chunks=["a", "b"], tool_uses=[tool], usage=Usage(10, 2)),
            FakeTurn(chunks=["done"]),
        ]
    )
    req = LLMRequest(system="s", messages=[{"role": "user", "content": "hi"}], max_tokens=2048)

    async def collect() -> list[list[TextDelta | LLMResponse]]:
        out = []
        for _ in range(2):
            out.append([event async for event in llm.stream(req)])
        return out

    first, second = asyncio.run(collect())
    assert first[:2] == [TextDelta("a"), TextDelta("b")]
    final = first[-1]
    assert isinstance(final, LLMResponse)
    assert final.text == "ab" and final.tool_uses == [tool] and final.stop_reason == "tool_use"
    assert final.usage == Usage(10, 2)
    assert isinstance(second[-1], LLMResponse) and second[-1].stop_reason == "end_turn"
    assert llm.requests == [req, req]


def test_fake_llm_blocks_until_released() -> None:
    async def scenario() -> list[str]:
        gate = asyncio.Event()
        llm = FakeLLM([FakeTurn(chunks=["x", "y"], block_on=gate, block_before_chunk=1)])
        seen: list[str] = []

        async def consume() -> None:
            async for event in llm.stream(LLMRequest(system="", messages=[], max_tokens=1)):
                if isinstance(event, TextDelta):
                    seen.append(event.text)

        task = asyncio.create_task(consume())
        for _ in range(5):
            await asyncio.sleep(0)
        assert seen == ["x"]
        gate.set()
        await task
        return seen

    assert asyncio.run(scenario()) == ["x", "y"]


def test_fake_search_and_notifier_record_calls() -> None:
    search = FakeSearch()
    notifier = FakeNotifier()
    alert = Alert(research_id=1, research_title="t", run_id=2, new_findings=1)

    async def go() -> int:
        results = await search.search("q", 5)
        await notifier.send_alert(alert)
        return len(results)

    assert asyncio.run(go()) == 1
    assert search.call_count == 1 and search.calls == [("q", 5)]
    assert notifier.outbox == [alert]
