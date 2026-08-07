"""Background Telegram getUpdates poller."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import Notification, User

logger = logging.getLogger(__name__)

CONNECT_RE = re.compile(r"^/start(?:@\w+)?\s+connectUser-(\d+)\s*$", re.IGNORECASE)
POLL_INTERVAL_SEC = 10


def _apply_connect(db: Session, user_id: int, telegram_id: int, message_at: datetime) -> None:
    user = db.get(User, user_id)
    if user is None:
        logger.info("Telegram connect ignored: unknown user_id=%s", user_id)
        return

    existing = db.get(Notification, user_id)
    if existing is not None:
        existing_at = existing.updated_at
        if existing_at.tzinfo is None:
            existing_at = existing_at.replace(tzinfo=UTC)
        if message_at <= existing_at:
            return
        existing.telegram_id = telegram_id
        existing.updated_at = message_at
    else:
        db.add(
            Notification(
                user_id=user_id,
                telegram_id=telegram_id,
                updated_at=message_at,
            )
        )
    db.commit()
    logger.info("Telegram linked user_id=%s telegram_id=%s", user_id, telegram_id)


def process_updates(updates: list[dict]) -> int | None:
    """Apply connectUser updates. Returns the next offset, or None if empty."""
    if not updates:
        return None

    next_offset = max(u["update_id"] for u in updates) + 1
    db = SessionLocal()
    try:
        for update in updates:
            message = update.get("message") or update.get("edited_message")
            if not message:
                continue
            text = (message.get("text") or "").strip()
            match = CONNECT_RE.match(text)
            if not match:
                continue
            chat = message.get("chat") or {}
            telegram_id = chat.get("id")
            if telegram_id is None:
                continue
            message_at = datetime.fromtimestamp(int(message["date"]), tz=UTC)
            _apply_connect(db, int(match.group(1)), int(telegram_id), message_at)
    finally:
        db.close()
    return next_offset


async def _fetch_updates(token: str, offset: int | None) -> list[dict]:
    params: dict[str, int] = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {payload}")
    return payload.get("result") or []


async def telegram_poll_loop(stop: asyncio.Event) -> None:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        return

    offset: int | None = None
    logger.info("Telegram poller started (every %ss)", POLL_INTERVAL_SEC)
    while not stop.is_set():
        try:
            updates = await _fetch_updates(token, offset)
            next_offset = process_updates(updates)
            if next_offset is not None:
                offset = next_offset
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram poller error")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL_SEC)
    logger.info("Telegram poller stopped")
