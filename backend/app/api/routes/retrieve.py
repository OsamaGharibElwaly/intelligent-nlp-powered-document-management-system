from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import document_repository
from app.dependencies import observability_metrics_store
from app.dependencies import retrieve_chunks_use_case
from app.request_context import current_request_metrics
from app.schemas.retrieval import RetrievalItem, RetrievalRequest
from app.services.observability_metrics_store import finalize_retrieve_metrics_row
from app.services.retrieval_scope import build_metadata_by_active_indexes, resolve_retrieval_documents

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=list[RetrievalItem])
async def retrieve_chunks(
    payload: RetrievalRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[dict[str, object], Depends(require_roles({"admin", "user", "viewer"}))],
) -> list[RetrievalItem]:
    req_metrics = current_request_metrics.get() or {}
    t_route = perf_counter()
    try:
        docs = resolve_retrieval_documents(
            user=user,
            document_repository=document_repository,
            document_id=payload.document_id,
            document_ids=payload.document_ids,
            filters=payload.filters,
        )
        metadata_by_index_document_id = build_metadata_by_active_indexes(document_repository, docs)
        if not metadata_by_index_document_id:
            elapsed = (perf_counter() - t_route) * 1000
            row = finalize_retrieve_metrics_row(
                req_metrics,
                retrieval_ms=elapsed,
                chunks_returned=0,
                top_relevance=None,
                success=True,
            )
            background_tasks.add_task(observability_metrics_store.append_event, row)
            return []

        results = await retrieve_chunks_use_case.execute(
            query=payload.query,
            document_id=(
                next(iter(metadata_by_index_document_id.keys()))
                if len(metadata_by_index_document_id) == 1
                else None
            ),
            top_k=payload.top_k,
            retrieval_mode=payload.retrieval_mode,
            metadata_by_index_document_id=metadata_by_index_document_id,
        )
        audit_service.log_event(
            action="document_access",
            user_id=str(user["sub"]),
            role=str(user.get("role", "")),
            document_id=payload.document_id or "multi-document",
            details={"endpoint": "retrieve", "top_k": payload.top_k, "retrieval_mode": payload.retrieval_mode},
        )
        items = [RetrievalItem(**result) for result in results]
        elapsed = (perf_counter() - t_route) * 1000
        top_rel = max((float(it.relevance_score) for it in items), default=None)
        row = finalize_retrieve_metrics_row(
            req_metrics,
            retrieval_ms=elapsed,
            chunks_returned=len(items),
            top_relevance=top_rel,
            success=True,
        )
        background_tasks.add_task(observability_metrics_store.append_event, row)
        return items
    except ValueError as exc:
        elapsed = (perf_counter() - t_route) * 1000
        row = finalize_retrieve_metrics_row(
            req_metrics,
            retrieval_ms=elapsed,
            chunks_returned=0,
            top_relevance=None,
            success=False,
            failure_detail=str(exc),
        )
        background_tasks.add_task(observability_metrics_store.append_event, row)
        message = str(exc).lower()
        status_code = 404 if "not found" in message else 403 if "deleted" in message or "access denied" in message else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
