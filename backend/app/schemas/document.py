from typing import Literal

from pydantic import BaseModel, Field


class DocumentVersionResponse(BaseModel):
    version: int
    filename: str
    file_size: int
    storage_path: str
    index_document_id: str
    index_status: str


class TodoItemResponse(BaseModel):
    todo_id: str
    title: str
    description: str | None = None
    status: Literal["pending", "done"]
    due_date: str | None = None
    completed_at: str | None = None


class DocumentMetadataResponse(BaseModel):
    document_id: str
    owner_id: str
    workspace_id: str | None = None
    collection_id: str
    filename: str
    active_version: int
    is_deleted: bool
    metadata_schema_version: int
    tags: list[str]
    metadata: dict[str, str]
    versions: list[DocumentVersionResponse]
    read_status: Literal["unread", "reading", "completed"] = "unread"
    completion_date: str | None = None
    last_read_at: str | None = None
    reading_progress: int = Field(default=0, ge=0, le=100)
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: str | None = None
    pinned: bool = False
    archived: bool = False
    ai_usage_count: int = Field(default=0, ge=0)
    todos: list[TodoItemResponse] = Field(default_factory=list)
    storage_schema_version: int = 1


class MetadataUpdateRequest(BaseModel):
    tags: list[str] | None = None
    metadata: dict[str, str] | None = None
