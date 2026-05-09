from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(default="New workspace", min_length=1, max_length=120)


class WorkspaceMemberRequest(BaseModel):
    email: EmailStr
    role: Literal["editor", "viewer"]


class DiscussionPostRequest(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class CommentCreateRequest(BaseModel):
    document_id: str = Field(min_length=1)
    thread_id: str | None = None
    answer_anchor: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=1, max_length=8000)
