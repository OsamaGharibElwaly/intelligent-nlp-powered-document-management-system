from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_repository
from app.dependencies import answer_question_use_case
from app.schemas.qa import AnswerRequest, AnswerResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=AnswerResponse)
async def query(
    payload: AnswerRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> AnswerResponse:
    try:
        document_repository.assert_access(user=user, document_id=payload.document_id)
        active = document_repository.get_active_version(payload.document_id)
        answer = await answer_question_use_case.execute(
            question=payload.question,
            document_id=str(active["index_document_id"]),
            top_k=payload.top_k,
        )
        audit_service.log_event(
            action="query",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=payload.document_id,
            details={"question": payload.question, "top_k": payload.top_k},
        )
        return AnswerResponse(answer=answer)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if ("access denied" in message or "deleted" in message) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
