from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import answer_question_use_case
from app.dependencies import document_repository
from app.schemas.qa import AnswerRequest, AnswerResponse
from app.services.rag_pipeline import zero_confidence_payload
from app.services.retrieval_scope import build_metadata_by_active_indexes, resolve_query_documents

router = APIRouter(tags=["query"])

_QUERY_QUALITY_CONF_THRESHOLD = 0.35


@router.post("/query", response_model=AnswerResponse)
async def query(
    payload: AnswerRequest,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> AnswerResponse:
    try:
        docs = resolve_query_documents(
            user=user,
            document_repository=document_repository,
            anchor_document_id=payload.document_id,
            document_ids=payload.document_ids,
            filters=payload.filters,
        )
        metadata_by_index_document_id = build_metadata_by_active_indexes(document_repository, docs)
        if not metadata_by_index_document_id:
            result = {
                "answer": "Not enough information in document",
                "citations": [],
                "confidence": zero_confidence_payload(),
                "evidence_spans": [],
            }
            return AnswerResponse.model_validate(result)

        result = await answer_question_use_case.execute(
            question=payload.question,
            document_id=None,
            top_k=payload.top_k,
            metadata_by_index_document_id=metadata_by_index_document_id,
            retrieval_mode=payload.retrieval_mode,
            answer_mode=payload.answer_mode,
            answer_length=payload.answer_length,
        )
        audit_service.log_event(
            action="query",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=payload.document_id,
            details={
                "question": payload.question,
                "top_k": payload.top_k,
                "answer_mode": payload.answer_mode,
                "answer_length": payload.answer_length,
                "retrieval_mode": payload.retrieval_mode,
                "multi_document": bool(payload.document_ids),
                "confidence_score": (result.get("confidence") or {}).get("score"),
                "answer_preview": str(result.get("answer", ""))[:400],
            },
        )
        conf = result.get("confidence") or {}
        score_raw = conf.get("score")
        try:
            score_f = float(score_raw) if score_raw is not None else 1.0
        except (TypeError, ValueError):
            score_f = 1.0
        ans_preview = str(result.get("answer", "")).strip()
        if score_f < _QUERY_QUALITY_CONF_THRESHOLD or ans_preview.startswith("Not enough information"):
            audit_service.log_event(
                action="query_quality_issue",
                user_id=str(user["sub"]),
                role=str(user.get("role", "")),
                document_id=payload.document_id,
                details={
                    "question": payload.question,
                    "confidence_score": score_f,
                    "answer_preview": ans_preview[:400],
                    "top_k": payload.top_k,
                },
            )
        return AnswerResponse.model_validate(result)
    except ValueError as exc:
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if ("access denied" in message or "deleted" in message) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
