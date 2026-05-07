from typing import Annotated

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_repository
from app.dependencies import ingest_document_use_case
from app.dependencies import quota_service
from app.dependencies import storage_service
from app.schemas.document import DocumentMetadataResponse, MetadataUpdateRequest

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentMetadataResponse])
async def list_documents(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    collection_id: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    metadata_key: str | None = Query(default=None),
    metadata_value: str | None = Query(default=None),
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
    return [DocumentMetadataResponse(**doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentMetadataResponse)
async def get_document(
    document_id: str,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> DocumentMetadataResponse:
    try:
        doc = document_repository.assert_access(user=user, document_id=document_id)
        audit_service.log_event(
            action="document_access",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"endpoint": "get_document"},
        )
        return DocumentMetadataResponse(**doc)
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
        document_repository.assert_access(user=user, document_id=document_id)
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
        audit_service.log_event(
            action="document_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"new_version": int(updated.get("active_version", 0))},
        )
        quota_service.record_upload(user=user, file_size=len(content))
        return DocumentMetadataResponse(**updated)
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
        document_repository.assert_access(user=user, document_id=document_id)
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
        return DocumentMetadataResponse(**doc)
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
        return DocumentMetadataResponse(**updated)
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
        audit_service.log_event(
            action="metadata_update",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=document_id,
            details={"tags_updated": payload.tags is not None, "metadata_updated": payload.metadata is not None},
        )
        return DocumentMetadataResponse(**updated)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
