from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import collaboration_comment_store
from app.dependencies import collaboration_thread_store
from app.dependencies import document_repository
from app.dependencies import notification_store
from app.dependencies import workspace_store
from app.services.notification_emitter import notify_new_comment
from app.schemas.collaboration import (
    CommentCreateRequest,
    DiscussionPostRequest,
    WorkspaceCreateRequest,
    WorkspaceMemberRequest,
)

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


def _assert_can_comment(*, user: dict[str, object], document_id: str) -> None:
    doc = document_repository.assert_access(user=user, document_id=document_id)
    wid = doc.get("workspace_id")
    if wid is None or str(wid).strip() == "":
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        return
    role_global = str(user.get("role", ""))
    email = str(user["sub"]).strip().lower()
    if role_global == "admin":
        return
    ws_role = workspace_store.member_role(str(wid).strip(), email)
    if ws_role not in ("owner", "editor"):
        raise ValueError("Comments require editor access in this workspace.")


@router.get("/workspaces")
async def list_workspaces(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> list[dict[str, object]]:
    rows = workspace_store.list_for_user(str(user["sub"]))
    return list(rows)


@router.post("/workspaces")
async def create_workspace(
    payload: WorkspaceCreateRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> dict[str, object]:
    try:
        row = workspace_store.create_workspace(owner_id=str(user["sub"]), name=payload.name.strip())
        return row
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/workspaces/{workspace_id}/members")
async def add_workspace_member(
    workspace_id: str,
    payload: WorkspaceMemberRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> dict[str, object]:
    try:
        actor = str(user["sub"])
        if str(user.get("role", "")) == "admin":
            return workspace_store.force_add_member(workspace_id.strip(), str(payload.email), payload.role)
        return workspace_store.add_or_update_member(
            workspace_id.strip(),
            actor_email=actor,
            member_email=str(payload.email),
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/workspaces/{workspace_id}/members/{member_email:path}")
async def remove_workspace_member(
    workspace_id: str,
    member_email: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> dict[str, object]:
    try:
        return workspace_store.remove_member(workspace_id.strip(), actor_email=str(user["sub"]), member_email=member_email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/threads")
async def list_threads(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> list[dict[str, object]]:
    try:
        document_repository.assert_access(user=user, document_id=document_id.strip())
        rows = collaboration_thread_store.list_for_document(document_id.strip())
        return list(rows)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 403, detail=str(exc)) from exc


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> dict[str, object]:
    row = collaboration_thread_store.get(thread_id.strip())
    if row is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    try:
        document_repository.assert_access(user=user, document_id=str(row["document_id"]))
        return dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/threads/{thread_id}/discussion")
async def post_discussion(
    thread_id: str,
    payload: DiscussionPostRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> dict[str, object]:
    row = collaboration_thread_store.get(thread_id.strip())
    if row is None:
        raise HTTPException(status_code=404, detail="Thread not found.")
    try:
        _assert_can_comment(user=user, document_id=str(row["document_id"]))
        updated = collaboration_thread_store.append_discussion(
            thread_id.strip(),
            user_id=str(user["sub"]),
            body=payload.body,
        )
        notify_new_comment(
            notification_store=notification_store,
            document_repository=document_repository,
            workspace_store=workspace_store,
            actor_email=str(user["sub"]),
            document_id=str(row["document_id"]),
            thread_id=thread_id.strip(),
            preview=payload.body,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comments")
async def list_comments(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    thread_id: str | None = None,
    document_id: str | None = None,
) -> list[dict[str, object]]:
    try:
        if thread_id:
            row = collaboration_thread_store.get(thread_id.strip())
            if row is None:
                raise ValueError("Thread not found.")
            document_repository.assert_access(user=user, document_id=str(row["document_id"]))
            return collaboration_comment_store.list_for_thread(thread_id.strip())
        if document_id:
            document_repository.assert_access(user=user, document_id=document_id.strip())
            return collaboration_comment_store.list_for_document(document_id.strip())
        raise ValueError("Specify thread_id or document_id.")
    except ValueError as exc:
        msg = str(exc).lower()
        code = 404 if "not found" in msg else 403 if "access denied" in msg else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/comments")
async def create_comment(
    payload: CommentCreateRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> dict[str, object]:
    try:
        document_repository.assert_access(user=user, document_id=payload.document_id.strip())
        _assert_can_comment(user=user, document_id=payload.document_id.strip())
        if payload.thread_id:
            th = collaboration_thread_store.get(payload.thread_id.strip())
            if th is None:
                raise ValueError("Thread not found.")
            if str(th.get("document_id")) != payload.document_id.strip():
                raise ValueError("Thread document mismatch.")
        row = collaboration_comment_store.create(
            user_id=str(user["sub"]),
            document_id=payload.document_id.strip(),
            body=payload.body,
            thread_id=payload.thread_id.strip() if payload.thread_id else None,
            answer_anchor=payload.answer_anchor,
        )
        notify_new_comment(
            notification_store=notification_store,
            document_repository=document_repository,
            workspace_store=workspace_store,
            actor_email=str(user["sub"]),
            document_id=payload.document_id.strip(),
            thread_id=payload.thread_id.strip() if payload.thread_id else None,
            preview=payload.body,
        )
        return row
    except ValueError as exc:
        msg = str(exc).lower()
        code = 404 if "not found" in msg else 403 if "access denied" in msg or "editor" in msg else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
