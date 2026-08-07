import asyncio
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Note, Notification, User
from app.notify_worker import find_due_notes, process_due_notifications


def _session(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'notify.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSession


def test_find_due_notes_filters(tmp_path):
    TestingSession = _session(tmp_path)
    db = TestingSession()
    linked = User(username="linked", password_hash="x")
    lonely = User(username="lonely", password_hash="x")
    db.add_all([linked, lonely])
    db.commit()
    db.refresh(linked)
    db.refresh(lonely)

    db.add(Notification(user_id=linked.id, telegram_id=111, updated_at=datetime.now(UTC)))
    today = date(2026, 8, 6)
    db.add_all(
        [
            Note(
                user_id=linked.id,
                title="due today",
                content="",
                note_date=today,
                notified_at=None,
            ),
            Note(
                user_id=linked.id,
                title="already sent",
                content="",
                note_date=today,
                notified_at=datetime.now(UTC),
            ),
            Note(
                user_id=linked.id,
                title="future",
                content="",
                note_date=today + timedelta(days=1),
                notified_at=None,
            ),
            Note(
                user_id=linked.id,
                title="no date",
                content="",
                note_date=None,
                notified_at=None,
            ),
            Note(
                user_id=lonely.id,
                title="no telegram",
                content="",
                note_date=today,
                notified_at=None,
            ),
            Note(
                user_id=linked.id,
                title="archived",
                content="",
                note_date=today,
                notified_at=None,
                archived_at=datetime.now(UTC),
            ),
        ]
    )
    db.commit()

    due = find_due_notes(db, today=today)
    assert len(due) == 1
    assert due[0][0].title == "due today"
    assert due[0][1].telegram_id == 111
    db.close()


def test_process_due_notifications_marks_sent(tmp_path, monkeypatch):
    TestingSession = _session(tmp_path)
    monkeypatch.setattr("app.notify_worker.SessionLocal", TestingSession)
    monkeypatch.setattr("app.notify_worker.settings.telegram_bot_token", "test-token")

    send = AsyncMock()
    monkeypatch.setattr("app.notify_worker.send_telegram_message", send)

    db = TestingSession()
    user = User(username="u", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Notification(user_id=user.id, telegram_id=42, updated_at=datetime.now(UTC)))
    note = Note(
        user_id=user.id,
        title="ping",
        content="body",
        note_date=date.today(),
        notified_at=None,
    )
    db.add(note)
    db.commit()
    note_id = note.id
    db.close()

    sent = asyncio.run(process_due_notifications())
    assert sent == 1
    send.assert_awaited_once()
    assert send.await_args.args[0] == 42
    assert "ping" in send.await_args.args[1]

    db = TestingSession()
    row = db.get(Note, note_id)
    assert row.notified_at is not None
    db.close()
