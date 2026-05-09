from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_activity_store
from app.dependencies import document_repository
from app.dependencies import ingest_document_use_case
from app.dependencies import quota_service
from app.dependencies import storage_service
from app.dependencies import notification_store
from app.dependencies import workspace_store
from app.schemas.upload import UploadResponse
from app.services.notification_emitter import notify_reindexed

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user"}))],
    collection_id: str = Form("default"),
    workspace_id: str | None = Form(default=None),
    file: UploadFile = File(...),
) -> UploadResponse:
    try:
        content = await file.read()
        quota_service.assert_upload_allowed(user=user, file_size=len(content))
        await file.seek(0)
        wid = (workspace_id or "").strip() or None
        if wid:
            role_g = str(user.get("role", ""))
            if role_g != "admin" and not workspace_store.can_edit_workspace_content(wid, str(user["sub"])):
                raise ValueError("Upload requires editor access in the target workspace.")
        result = await ingest_document_use_case.execute(file)
        file_path = storage_service.save_document(result["document_id"], file.filename or "document", content, version=1)
        document_repository.create(
            document_id=result["document_id"],
            owner_id=str(user["sub"]),
            collection_id=collection_id.strip() or "default",
            filename=file.filename or "document",
            file_size=len(content),
            storage_path=file_path,
            index_document_id=result["document_id"],
            workspace_id=wid,
        )
        did = result["document_id"]
        document_activity_store.append(
            document_id=did,
            activity_type="uploaded",
            user_id=str(user["sub"]),
            details={
                "filename": file.filename or "document",
                "collection_id": collection_id.strip() or "default",
                "workspace_id": wid,
            },
        )
        document_activity_store.append(
            document_id=did,
            activity_type="reindexed",
            user_id=str(user["sub"]),
            details={"version": 1, "index_document_id": did},
        )
        audit_service.log_event(
            action="document_upload",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=did,
            details={
                "filename": file.filename or "document",
                "collection_id": collection_id.strip() or "default",
                "workspace_id": wid,
            },
        )
        notify_reindexed(
            notification_store=notification_store,
            document_repository=document_repository,
            workspace_store=workspace_store,
            actor_email=str(user["sub"]),
            document_id=did,
            context=f"Uploaded and indexed · {file.filename or 'document'}",
        )
        quota_service.record_upload(user=user, file_size=len(content))
        return UploadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
