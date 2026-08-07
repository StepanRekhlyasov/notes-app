"""Telegram Bot API helpers."""

from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(chat_id: int, text: str) -> None:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")
