from typing import Literal

from pydantic import BaseModel, Field

ReadStatus = Literal["unread", "reading", "completed"]
Priority = Literal["low", "medium", "high"]
TodoStatus = Literal["pending", "done"]

DOCUMENT_ACTIVITY_TYPES = frozenset(
    {
        "uploaded",
        "opened_read",
        "marked_completed",
        "annotated",
        "reindexed",
        "archived",
        "ai_answer_used",
    }
)


class DocumentLifecyclePatch(BaseModel):
    read_status: ReadStatus | None = None
    completion_date: str | None = None
    last_read_at: str | None = None
    reading_progress: int | None = Field(default=None, ge=0, le=100)
    priority: Priority | None = None
    due_date: str | None = None
    pinned: bool | None = None
    archived: bool | None = None


class DocumentReadProgressRequest(BaseModel):
    reading_progress: int = Field(ge=0, le=100)


class TodoCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    due_date: str | None = None
    status: TodoStatus = "pending"


class TodoPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = None
    due_date: str | None = None
    status: TodoStatus | None = None


class ActivityEntryResponse(BaseModel):
    activity_id: str
    document_id: str
    activity_type: str
    timestamp: str
    user_id: str
    details: dict[str, object] = Field(default_factory=dict)
