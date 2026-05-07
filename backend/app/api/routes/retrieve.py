from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_repository
from app.dependencies import retrieve_chunks_use_case
from app.schemas.retrieval import RetrievalItem, RetrievalRequest

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=list[RetrievalItem])
async def retrieve_chunks(
    payload: RetrievalRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> list[RetrievalItem]:
    try:
        document_repository.assert_access(user=user, document_id=payload.document_id)
        active = document_repository.get_active_version(payload.document_id)
        results = await retrieve_chunks_use_case.execute(
            query=payload.query,
            document_id=str(active["index_document_id"]),
            top_k=payload.top_k,
        )
        audit_service.log_event(
            action="document_access",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=payload.document_id,
            details={"endpoint": "retrieve", "top_k": payload.top_k},
        )
        return [RetrievalItem(**result) for result in results]
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "deleted" in message or "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
