"""Select real or fake integrations from Settings."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.integrations.anthropic_llm import AnthropicLLM
from app.integrations.fakes import FakeLLM, FakeNotifier, FakeSearch
from app.integrations.llm import LLMClient
from app.integrations.notifier import Notifier
from app.integrations.search import SearchClient
from app.integrations.tavily import TavilySearch
from app.integrations.telegram_notifier import TelegramNotifier


class FakeModeInProduction(RuntimeError):
    pass


@dataclass(frozen=True)
class Integrations:
    llm: LLMClient
    search: SearchClient
    notifier: Notifier


def get_integrations(settings: Settings | None = None) -> Integrations:
    settings = settings if settings is not None else get_settings()
    if settings.integrations_mode == "fake":
        if settings.app_env == "production":  # defense in depth; Settings also refuses
            raise FakeModeInProduction("INTEGRATIONS_MODE=fake is not allowed in production")
        return Integrations(
            llm=FakeLLM(chunk_delay_ms=settings.fake_llm_chunk_delay_ms),
            search=FakeSearch(),
            notifier=FakeNotifier(),
        )
    return Integrations(
        llm=AnthropicLLM(api_key=settings.anthropic_api_key, model=settings.anthropic_model),
        search=TavilySearch(api_key=settings.tavily_api_key),
        notifier=TelegramNotifier(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.owner_chat_id,
            public_base_url=settings.public_base_url,
        ),
    )
