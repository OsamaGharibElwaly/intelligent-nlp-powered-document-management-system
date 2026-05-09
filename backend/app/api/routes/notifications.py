from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_roles
from app.dependencies import notification_store
from app.schemas.notification import NotificationItem, NotificationMarkReadResponse, NotificationUnreadCount

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _validate_item(raw: dict[str, object]) -> NotificationItem:
    link_raw = raw.get("link")
    link_dict = link_raw if isinstance(link_raw, dict) else {}
    return NotificationItem.model_validate(
        {
            **raw,
            "link": link_dict,
        }
    )


@router.get("", response_model=list[NotificationItem])
async def list_notifications(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    limit: int = Query(default=80, ge=1, le=200),
    unread_only: bool = Query(default=False),
) -> list[NotificationItem]:
    rows = notification_store.list_for_user(str(user["sub"]), limit=limit, unread_only=unread_only)
    return [_validate_item(dict(r)) for r in rows]


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def unread_count(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> NotificationUnreadCount:
    return NotificationUnreadCount(unread=notification_store.unread_count(str(user["sub"])))


@router.patch("/{notification_id}/read", response_model=NotificationMarkReadResponse)
async def mark_notification_read(
    notification_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> NotificationMarkReadResponse:
    updated = notification_store.mark_read(str(user["sub"]), notification_id.strip())
    if updated is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return NotificationMarkReadResponse(notification=_validate_item(updated))


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> dict[str, int]:
    n = notification_store.mark_all_read(str(user["sub"]))
    return {"marked": n}
