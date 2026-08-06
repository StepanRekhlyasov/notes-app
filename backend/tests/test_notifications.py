from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import deps
from app.db import Base
from app.main import app
from app.models import Notification, User
from app.telegram_poller import process_updates


def _register_login(client, username="user1", password="pw123456"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    r = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _db():
    return next(app.dependency_overrides[deps.get_db]())


def test_notifications_link_then_connected(client):
    h = _register_login(client)

    r = client.get("/api/notifications", headers=h)
    assert r.status_code == 200
    url = r.json()["url"]
    assert "t.me/suboid_bot?start=connectUser-" in url
    user_id = int(url.rsplit("-", 1)[-1])

    db = _db()
    try:
        db.add(Notification(user_id=user_id, telegram_id=381864232, updated_at=datetime.now(UTC)))
        db.commit()
    finally:
        db.close()

    r = client.get("/api/notifications", headers=h)
    assert r.status_code == 201
    assert r.content == b""


def test_disconnect_notifications(client):
    h = _register_login(client, "alice", "pw123456")
    r = client.get("/api/notifications", headers=h)
    user_id = int(r.json()["url"].rsplit("-", 1)[-1])

    db = _db()
    try:
        db.add(Notification(user_id=user_id, telegram_id=99, updated_at=datetime.now(UTC)))
        db.commit()
    finally:
        db.close()

    r = client.delete("/api/notifications", headers=h)
    assert r.status_code == 204

    r = client.get("/api/notifications", headers=h)
    assert r.status_code == 200
    assert "connectUser-" in r.json()["url"]


def test_process_updates_upserts_by_message_date(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'poll.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, future=True)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.telegram_poller.SessionLocal", TestingSession)

    db = TestingSession()
    user = User(username="bob", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    older = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
    newer = int(datetime.now(UTC).timestamp())

    offset = process_updates(
        [
            {
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "date": older,
                    "text": f"/start connectUser-{user_id}",
                    "chat": {"id": 111, "type": "private"},
                },
            }
        ]
    )
    assert offset == 2

    db = TestingSession()
    row = db.get(Notification, user_id)
    assert row is not None
    assert row.telegram_id == 111
    first_updated = row.updated_at
    db.close()

    process_updates(
        [
            {
                "update_id": 2,
                "message": {
                    "message_id": 2,
                    "date": older,
                    "text": f"/start connectUser-{user_id}",
                    "chat": {"id": 222, "type": "private"},
                },
            }
        ]
    )
    db = TestingSession()
    row = db.get(Notification, user_id)
    assert row.telegram_id == 111
    db.close()

    process_updates(
        [
            {
                "update_id": 3,
                "message": {
                    "message_id": 3,
                    "date": newer,
                    "text": f"/start connectUser-{user_id}",
                    "chat": {"id": 333, "type": "private"},
                },
            }
        ]
    )
    db = TestingSession()
    row = db.get(Notification, user_id)
    assert row.telegram_id == 333
    assert row.updated_at >= first_updated
    db.close()
