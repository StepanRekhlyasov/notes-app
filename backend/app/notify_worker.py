"""Background worker: notify users about due dated notes via Telegram."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import Note, Notification
from .telegram import send_telegram_message

logger = logging.getLogger(__name__)

NOTIFY_INTERVAL_SEC = 10


def _format_message(note: Note) -> str:
    lines = [f"📅 Reminder: {note.title}"]
    if note.note_date is not None:
        lines.append(f"Date: {note.note_date.isoformat()}")
    body = (note.content or "").strip()
    if body:
        preview = body if len(body) <= 500 else f"{body[:497]}..."
        lines.append("")
        lines.append(preview)
    return "\n".join(lines)


def find_due_notes(db: Session, today: date | None = None) -> list[tuple[Note, Notification]]:
    """Notes with note_date <= today, not yet notified, for users with Telegram linked."""
    if today is None:
        today = date.today()
    rows = (
        db.query(Note, Notification)
        .join(Notification, Notification.user_id == Note.user_id)
        .filter(
            Note.note_date.is_not(None),
            Note.note_date <= today,
            Note.notified_at.is_(None),
            Note.archived_at.is_(None),
        )
        .order_by(Note.note_date.asc(), Note.id.asc())
        .all()
    )
    return list(rows)


async def process_due_notifications() -> int:
    """Send reminders for due notes. Returns number of successfully notified notes."""
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        return 0

    db = SessionLocal()
    sent = 0
    try:
        due = find_due_notes(db)
        for note, link in due:
            try:
                await send_telegram_message(link.telegram_id, _format_message(note))
            except Exception:
                logger.exception("Failed to notify note_id=%s user_id=%s", note.id, note.user_id)
                continue
            note.notified_at = datetime.now(UTC)
            db.commit()
            sent += 1
            logger.info("Notified note_id=%s user_id=%s", note.id, note.user_id)
    finally:
        db.close()
    return sent


async def notify_worker_loop(stop: asyncio.Event) -> None:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        return

    logger.info("Notify worker started (every %ss)", NOTIFY_INTERVAL_SEC)
    while not stop.is_set():
        try:
            await process_due_notifications()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notify worker error")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=NOTIFY_INTERVAL_SEC)
    logger.info("Notify worker stopped")
