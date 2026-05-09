from pydantic import BaseModel, Field


class NotificationLink(BaseModel):
    document_id: str | None = None
    thread_id: str | None = None
    panel: str | None = Field(default=None, description="documents | query")


class NotificationItem(BaseModel):
    notification_id: str
    user_id: str
    type: str
    category: str
    title: str
    body: str = ""
    read: bool = False
    created_at: str
    link: NotificationLink = Field(default_factory=NotificationLink)


class NotificationUnreadCount(BaseModel):
    unread: int


class NotificationMarkReadResponse(BaseModel):
    notification: NotificationItem | None = None
