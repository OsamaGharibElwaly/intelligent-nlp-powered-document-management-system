from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import answer_question_use_case
from app.dependencies import collaboration_thread_store
from app.dependencies import document_activity_store
from app.dependencies import document_repository
from app.dependencies import notification_store
from app.dependencies import observability_metrics_store
from app.dependencies import workspace_store
from app.request_context import current_request_metrics
from app.schemas.qa import AnswerRequest, AnswerResponse
from app.services.answer_usage_recorder import record_answer_document_usage, split_answer_result
from app.services.notification_emitter import notify_ai_answer, notify_query_failed
from app.services.observability_metrics_store import finalize_query_metrics_row
from app.services.rag_pipeline import zero_confidence_payload
from app.services.retrieval_scope import build_metadata_by_active_indexes, resolve_query_documents

router = APIRouter(tags=["query"])

_QUERY_QUALITY_CONF_THRESHOLD = 0.35


def _persist_query_thread(*, user: dict[str, object], payload: AnswerRequest, answer_dict: dict[str, object]) -> str:
    uid = str(user["sub"])
    doc_meta = document_repository.get(payload.document_id)
    if doc_meta is None:
        raise ValueError("Document not found.")
    document_repository.assert_access(user=user, document_id=payload.document_id)
    ws_raw = doc_meta.get("workspace_id")
    ws_key: str | None = None if ws_raw is None or str(ws_raw).strip() == "" else str(ws_raw).strip()
    tid_in = (payload.thread_id or "").strip()
    if tid_in:
        existing = collaboration_thread_store.get(tid_in)
        if existing is None:
            raise ValueError("Thread not found.")
        if str(existing.get("document_id")) != payload.document_id.strip():
            raise ValueError("Thread document mismatch.")
        collaboration_thread_store.append_turn(
            tid_in,
            created_by=uid,
            question=payload.question,
            answer_payload=answer_dict,
        )
        return tid_in
    row = collaboration_thread_store.create_thread(
        document_id=payload.document_id.strip(),
        workspace_id=ws_key,
        created_by=uid,
        question=payload.question,
        answer_payload=answer_dict,
    )
    return str(row["thread_id"])


def _answer_response_with_thread(base_dict: dict[str, object], thread_id: str | None) -> AnswerResponse:
    parsed = AnswerResponse.model_validate(base_dict)
    data = parsed.model_dump()
    data["thread_id"] = thread_id
    return AnswerResponse(**data)


@router.post("/query", response_model=AnswerResponse)
async def query(
    payload: AnswerRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> AnswerResponse:
    req_metrics = current_request_metrics.get()
    if req_metrics is None:
        req_metrics = {}
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
            row = finalize_query_metrics_row(req_metrics, result, success=True, short_circuit=True, endpoint="/query")
            background_tasks.add_task(observability_metrics_store.append_event, row)
            thread_out: str | None = None
            if payload.persist_thread:
                thread_out = _persist_query_thread(user=user, payload=payload, answer_dict=result)
            resp = _answer_response_with_thread(result, thread_out)
            notify_ai_answer(
                notification_store=notification_store,
                document_repository=document_repository,
                workspace_store=workspace_store,
                actor_email=str(user["sub"]),
                document_id=payload.document_id.strip(),
                thread_id=thread_out,
                question_preview=payload.question,
            )
            return resp

        result = await answer_question_use_case.execute(
            question=payload.question,
            document_id=None,
            top_k=payload.top_k,
            metadata_by_index_document_id=metadata_by_index_document_id,
            retrieval_mode=payload.retrieval_mode,
            answer_mode=payload.answer_mode,
            answer_length=payload.answer_length,
        )
        cleaned, usage_ids = split_answer_result(result)
        record_answer_document_usage(
            document_repository=document_repository,
            activity_store=document_activity_store,
            audit_service=audit_service,
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            anchor_document_id=payload.document_id,
            usage_document_ids=usage_ids,
            question_preview=payload.question,
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
                "confidence_score": (cleaned.get("confidence") or {}).get("score"),
                "answer_preview": str(cleaned.get("answer", ""))[:400],
            },
        )
        conf = cleaned.get("confidence") or {}
        score_raw = conf.get("score")
        try:
            score_f = float(score_raw) if score_raw is not None else 1.0
        except (TypeError, ValueError):
            score_f = 1.0
        ans_preview = str(cleaned.get("answer", "")).strip()
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
        row = finalize_query_metrics_row(req_metrics, cleaned, success=True, endpoint="/query")
        background_tasks.add_task(observability_metrics_store.append_event, row)
        thread_out = None
        if payload.persist_thread:
            thread_out = _persist_query_thread(user=user, payload=payload, answer_dict=cleaned)
        resp = _answer_response_with_thread(cleaned, thread_out)
        notify_ai_answer(
            notification_store=notification_store,
            document_repository=document_repository,
            workspace_store=workspace_store,
            actor_email=str(user["sub"]),
            document_id=payload.document_id.strip(),
            thread_id=thread_out,
            question_preview=payload.question,
        )
        return resp
    except ValueError as exc:
        row = finalize_query_metrics_row(req_metrics, None, success=False, failure_detail=str(exc), endpoint="/query")
        background_tasks.add_task(observability_metrics_store.append_event, row)
        notify_query_failed(
            notification_store=notification_store,
            user_email=str(user["sub"]),
            document_id=str(payload.document_id).strip(),
            detail=str(exc),
        )
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if ("access denied" in message or "deleted" in message) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
