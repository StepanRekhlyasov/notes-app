from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import get_current_user, get_db
from ..models import Notification, User
from ..schemas import NotificationLinkOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=None)
def get_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | NotificationLinkOut:
    existing = db.get(Notification, user.id)
    if existing is not None:
        return Response(status_code=status.HTTP_201_CREATED)

    bot = settings.telegram_bot_username.lstrip("@")
    url = f"https://t.me/{bot}?start=connectUser-{user.id}"
    return NotificationLinkOut(url=url)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    existing = db.get(Notification, user.id)
    if existing is not None:
        db.delete(existing)
        db.commit()
