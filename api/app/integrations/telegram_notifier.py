"""Telegram adapter for Notifier. Implemented in M12."""

from __future__ import annotations

from app.integrations.notifier import Alert, Notifier


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: int, public_base_url: str) -> None:
        self._bot_token = bot_token
        self.chat_id = chat_id
        self.public_base_url = public_base_url

    def __repr__(self) -> str:
        return f"TelegramNotifier(chat_id={self.chat_id})"

    async def send_alert(self, alert: Alert) -> None:
        raise NotImplementedError("TelegramNotifier.send_alert is implemented in M12")


_conforms: type[Notifier] = TelegramNotifier
