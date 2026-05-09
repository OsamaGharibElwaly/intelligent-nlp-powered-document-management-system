from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_repository
from app.dependencies import feedback_store
from app.dependencies import learning_signals_store
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])

_LOW_CONF_THRESHOLD = 0.35


def _should_flag_reindex(payload: FeedbackRequest) -> bool:
    if payload.sentiment != "negative":
        return False
    ans = (payload.answer or "").strip()
    if ans.startswith("Not enough information"):
        return True
    if payload.confidence_score is not None and payload.confidence_score < _LOW_CONF_THRESHOLD:
        return True
    return False


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> FeedbackResponse:
    try:
        document_repository.assert_access(user=user, document_id=payload.document_id)
        chunk_ids = [str(c.chunk_id) for c in payload.retrieved_chunks]

        record = {
            "user_id": str(user["sub"]),
            "role": str(user.get("role", "")),
            "sentiment": payload.sentiment,
            "query": payload.query.strip(),
            "logical_document_id": payload.document_id,
            "answer_snapshot": payload.answer,
            "confidence_score_at_feedback": payload.confidence_score,
            "retrieved_chunks_snapshot": [c.model_dump() for c in payload.retrieved_chunks],
            "interaction_id": payload.interaction_id,
        }
        feedback_id = feedback_store.append(record)

        learning_signals_store.apply_feedback_to_chunks(chunk_ids, positive=payload.sentiment == "positive")
        learning_signals_store.nudge_hybrid_weights(positive=payload.sentiment == "positive")
        if _should_flag_reindex(payload):
            learning_signals_store.flag_reindex(
                payload.document_id,
                reason="negative_or_low_confidence_feedback",
            )

        audit_service.log_event(
            action="user_feedback",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=payload.document_id,
            details={
                "feedback_id": feedback_id,
                "sentiment": payload.sentiment,
                "chunks_affected": len(chunk_ids),
            },
        )
        return FeedbackResponse(feedback_id=feedback_id)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if ("access denied" in message or "deleted" in message) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
