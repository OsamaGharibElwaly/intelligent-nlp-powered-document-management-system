from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import require_roles
from app.dependencies import audit_service
from app.schemas.audit import AuditLogEntryResponse, UsageHistoryResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogEntryResponse])
async def list_audit_logs(
    user: Annotated[dict[str, object], Depends(require_roles({"admin"}))],
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[AuditLogEntryResponse]:
    _ = user
    entries = audit_service.list_events(user_id=actor, action=action, document_id=document_id, limit=limit)
    return [AuditLogEntryResponse(**entry) for entry in entries]


@router.get("/usage-history", response_model=UsageHistoryResponse)
async def usage_history(
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
    limit: int = Query(default=50, ge=1, le=500),
) -> UsageHistoryResponse:
    user_id = str(user["sub"])
    query_entries = audit_service.list_events(user_id=user_id, action="query", limit=limit)
    last_docs = audit_service.last_accessed_documents(user_id=user_id, limit=20)
    return UsageHistoryResponse(
        user_id=user_id,
        query_history=[AuditLogEntryResponse(**entry) for entry in query_entries],
        last_accessed_documents=last_docs,
    )
