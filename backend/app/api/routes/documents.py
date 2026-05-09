from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_activity_store
from app.dependencies import document_repository
from app.dependencies import ingest_document_use_case
from app.dependencies import notification_store
from app.dependencies import quota_service
from app.dependencies import storage_service
from app.dependencies import workspace_store
from app.schemas.document import DocumentMetadataResponse, MetadataUpdateRequest
from app.schemas.document_storage import (
    DOCUMENT_ACTIVITY_TYPES,
    ActivityEntryResponse,
    DocumentLifecyclePatch,
    DocumentReadProgressRequest,
    TodoCreateRequest,
    TodoPatchRequest,
)
from app.services.document_storage_filters import apply_storage_filters, sort_documents
from app.services.notification_emitter import notify_document_updated, notify_reindexed

router = APIRouter(prefix="/documents", tags=["documents"])


def _notify_document_updated(*, user: dict[str, object], document_id: str, summary: str) -> None:
    notify_document_updated(
        notification_store=notification_store,
        document_repository=document_repository,
        workspace_store=workspace_store,
        actor_email=str(user["sub"]),
        document_id=document_id,
        summary=summary,
    )


def _maybe_activity_marked_completed(
    *,
    document_id: str,
    user_id: str,
    before: dict[str, object],
    updated: dict[str, object],
    details: dict[str, object] | None = None,
) -> None:
    if str(updated.get("read_status", "")).lower() != "completed":
        return
    if str(before.get("read_status", "")).lower() == "completed":
        return
    merged = {"completion_date": updated.get("completion_date")}
    if details:
        merged.update(details)
    document_activity_store.append(
        document_id=document_id,
        activity_type="marked_completed",
        user_id=user_id,
        details=merged,
    )


def _lifecycle_activity_hooks(
    *,
    document_id: str,
    user_id: str,
    before: dict[str, object],
    patch: DocumentLifecyclePatch,
) -> None:
    if patch.archived is True and not bool(before.get("archived", False)):
        document_activity_store.append(
            document_id=document_id,
            activity_type="archived",
            user_id=user_id,
            details={"previous_archived": False},
        )


@router.get("", response_model=list[DocumentMetadataResponse])
async def list_documents(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    collection_id: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    metadata_key: str | None = Query(default=None),
    metadata_value: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    read_status: str | None = Query(default=None),
    in_progress: bool | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    priority: str | None = Query(default=None),
    pinned_only: bool | None = Query(default=None),
    sort: str | None = Query(default=None, description="recently_read | due_date_asc | priority_desc"),
) -> list[DocumentMetadataResponse]:
    docs = document_repository.list_for_user(user)
    if collection_id:
        docs = [doc for doc in docs if str(doc.get("collection_id", "")) == collection_id]
    if tag:
        expected_tag = tag.strip().lower()
        docs = [doc for doc in docs if expected_tag in list(doc.get("tags", []))]
    if metadata_key:
        docs = [doc for doc in docs if metadata_key in dict(doc.get("metadata", {}))]
    if metadata_key and metadata_value is not None:
        docs = [doc for doc in docs if str(dict(doc.get("metadata", {})).get(metadata_key, "")) == metadata_value]

    docs = apply_storage_filters(
        docs,
        read_status=read_status,
        in_progress=in_progress if in_progress is not None else None,
        overdue=overdue if overdue is not None else None,
        priority=priority,
        pinned_only=pinned_only if pinned_only is not None else None,
        include_archived=include_archived,
    )
    docs = sort_documents(docs, sort)
    return [DocumentMetadataResponse.model_validate(doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
async def get_document(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> DocumentMetadataResponse:
    try:
        doc = document_repository.assert_access(user=user, document_id=document_id)
        document_activity_store.append(
            document_id=document_id,
            activity_type="opened_read",
            user_id=str(user["sub"]),
            details={"endpoint": "get_document"},
        )
        audit_service.log_event(
            action="document_access",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"endpoint": "get_document"},
        )
        return DocumentMetadataResponse.model_validate(doc)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 403, detail=str(exc)) from exc


@router.get("/{document_id}/versions", response_model=list[dict[str, object]])
async def list_document_versions(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> list[dict[str, object]]:
    try:
        doc = document_repository.assert_access(user=user, document_id=document_id)
        audit_service.log_event(
            action="document_access",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"endpoint": "list_document_versions"},
        )
        return list(doc.get("versions", []))
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc).lower() else 403, detail=str(exc)) from exc


@router.post("/{document_id}/versions", response_model=DocumentMetadataResponse)
async def create_new_version(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
    file: UploadFile = File(...),
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        content = await file.read()
        quota_service.assert_upload_allowed(user=user, file_size=len(content))
        doc = document_repository.get(document_id)
        if doc is None:
            raise ValueError("Document not found.")
        current_versions = list(doc.get("versions", []))
        next_version = len(current_versions) + 1
        index_document_id = f"{document_id}:v{next_version}"
        await file.seek(0)
        await ingest_document_use_case.execute(file=file, index_document_id=index_document_id)
        path = storage_service.save_document(document_id, file.filename or "document", content, version=next_version)
        updated = document_repository.append_version(
            document_id=document_id,
            filename=file.filename or "document",
            file_size=len(content),
            storage_path=path,
            index_document_id=index_document_id,
        )
        document_activity_store.append(
            document_id=document_id,
            activity_type="reindexed",
            user_id=str(user["sub"]),
            details={"version": int(updated.get("active_version", 0)), "index_document_id": index_document_id},
        )
        audit_service.log_event(
            action="document_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"new_version": int(updated.get("active_version", 0))},
        )
        quota_service.record_upload(user=user, file_size=len(content))
        notify_reindexed(
            notification_store=notification_store,
            document_repository=document_repository,
            workspace_store=workspace_store,
            actor_email=str(user["sub"]),
            document_id=document_id,
            context=f"New version indexed · v{int(updated.get('active_version', 0))} · {file.filename or 'document'}",
        )
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{document_id}/delete", response_model=DocumentMetadataResponse)
async def soft_delete_document(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        document_repository.soft_delete(document_id=document_id)
        doc = document_repository.get(document_id)
        if doc is None:
            raise ValueError("Document not found.")
        audit_service.log_event(
            action="document_delete",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"soft_delete": True},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Document moved to trash.")
        return DocumentMetadataResponse.model_validate(doc)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{document_id}/restore", response_model=DocumentMetadataResponse)
async def restore_document(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
    version: int | None = Form(default=None),
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        updated = document_repository.restore(document_id=document_id, version=version)
        audit_service.log_event(
            action="document_restore",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"restored_version": int(updated.get("active_version", 1))},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Document restored from trash.")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/{document_id}/metadata", response_model=DocumentMetadataResponse)
async def update_document_metadata(
    document_id: str,
    payload: MetadataUpdateRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        updated = document_repository.update_metadata(
            document_id=document_id,
            tags=payload.tags,
            metadata=payload.metadata,
        )
        document_activity_store.append(
            document_id=document_id,
            activity_type="annotated",
            user_id=str(user["sub"]),
            details={"tags_updated": payload.tags is not None, "metadata_updated": payload.metadata is not None},
        )
        audit_service.log_event(
            action="metadata_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"tags_updated": payload.tags is not None, "metadata_updated": payload.metadata is not None},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Metadata or tags were updated.")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/{document_id}/state", response_model=DocumentMetadataResponse)
async def patch_document_state(
    document_id: str,
    payload: DocumentLifecyclePatch,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        before = document_repository.get(document_id)
        if before is None:
            raise ValueError("Document not found.")
        updated = document_repository.update_lifecycle_state(
            document_id,
            read_status=payload.read_status,
            completion_date=payload.completion_date,
            last_read_at=payload.last_read_at,
            reading_progress=payload.reading_progress,
            priority=payload.priority,
            due_date=payload.due_date,
            pinned=payload.pinned,
            archived=payload.archived,
        )
        _lifecycle_activity_hooks(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            patch=payload,
        )
        _maybe_activity_marked_completed(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            updated=dict(updated),
            details={"reason": "lifecycle_patch"},
        )
        audit_service.log_event(
            action="document_storage_state_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"patch": payload.model_dump(exclude_none=True)},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Document lifecycle or organization fields changed.")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{document_id}/read-progress", response_model=DocumentMetadataResponse)
async def post_read_progress(
    document_id: str,
    payload: DocumentReadProgressRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_access(user=user, document_id=document_id)
        before = document_repository.get(document_id)
        if before is None:
            raise ValueError("Document not found.")
        updated = document_repository.record_read_progress(document_id, payload.reading_progress)
        _maybe_activity_marked_completed(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            updated=dict(updated),
            details={"reason": "reading_progress", "reading_progress": payload.reading_progress},
        )
        document_activity_store.append(
            document_id=document_id,
            activity_type="opened_read",
            user_id=str(user["sub"]),
            details={"reading_progress": payload.reading_progress},
        )
        audit_service.log_event(
            action="document_read_progress",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"reading_progress": payload.reading_progress},
        )
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{document_id}/activity", response_model=list[ActivityEntryResponse])
async def list_document_activity(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    activity_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> list[ActivityEntryResponse]:
    try:
        document_repository.assert_access(user=user, document_id=document_id)
        if activity_type and activity_type.strip().lower() not in DOCUMENT_ACTIVITY_TYPES:
            raise ValueError("Invalid activity_type filter.")
        rows = document_activity_store.list_for_document(
            document_id,
            activity_type=activity_type.strip().lower() if activity_type else None,
            limit=limit,
        )
        return [ActivityEntryResponse.model_validate(row) for row in rows]
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 400 if "invalid" in message else 404 if "not found" in message else 403
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{document_id}/todos", response_model=DocumentMetadataResponse)
async def create_document_todo(
    document_id: str,
    payload: TodoCreateRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        before = document_repository.get(document_id)
        if before is None:
            raise ValueError("Document not found.")
        updated = document_repository.create_todo(
            document_id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            status=payload.status,
        )
        _maybe_activity_marked_completed(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            updated=dict(updated),
            details={"reason": "all_todos_done"},
        )
        audit_service.log_event(
            action="document_todo_create",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"title": payload.title[:120]},
        )
        _notify_document_updated(user=user, document_id=document_id, summary=f"New todo · {payload.title[:120]}")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/{document_id}/todos/{todo_id}", response_model=DocumentMetadataResponse)
async def patch_document_todo(
    document_id: str,
    todo_id: str,
    payload: TodoPatchRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        before = document_repository.get(document_id)
        if before is None:
            raise ValueError("Document not found.")
        updated = document_repository.update_todo(
            document_id,
            todo_id,
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
            status=payload.status,
        )
        _maybe_activity_marked_completed(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            updated=dict(updated),
            details={"reason": "all_todos_done"},
        )
        audit_service.log_event(
            action="document_todo_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"todo_id": todo_id, "patch": payload.model_dump(exclude_none=True)},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Todo updated.")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{document_id}/todos/{todo_id}", response_model=DocumentMetadataResponse)
async def delete_document_todo(
    document_id: str,
    todo_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
) -> DocumentMetadataResponse:
    try:
        document_repository.assert_owner_or_admin(user=user, document_id=document_id)
        before = document_repository.get(document_id)
        if before is None:
            raise ValueError("Document not found.")
        updated = document_repository.delete_todo(document_id, todo_id)
        _maybe_activity_marked_completed(
            document_id=document_id,
            user_id=str(user["sub"]),
            before=dict(before),
            updated=dict(updated),
            details={"reason": "all_todos_done"},
        )
        audit_service.log_event(
            action="document_todo_delete",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"todo_id": todo_id},
        )
        _notify_document_updated(user=user, document_id=document_id, summary="Todo removed.")
        return DocumentMetadataResponse.model_validate(updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
