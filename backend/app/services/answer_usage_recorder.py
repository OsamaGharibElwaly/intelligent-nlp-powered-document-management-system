"""Record which logical documents contributed to an AI answer (storage counter + timeline)."""

from typing import Any

from app.services.audit_service import AuditService
from app.services.document_activity_store import DocumentActivityStore
from app.services.document_repository import DocumentRepository


def record_answer_document_usage(
    *,
    document_repository: DocumentRepository,
    activity_store: DocumentActivityStore,
    audit_service: AuditService,
    user_id: str,
    role: str,
    anchor_document_id: str | None,
    usage_document_ids: list[str],
    question_preview: str,
) -> None:
    logical = {str(x).strip() for x in usage_document_ids if str(x).strip()}
    if not logical:
        return
    document_repository.bulk_increment_ai_usage(logical)
    for lid in sorted(logical):
        activity_store.append(
            document_id=lid,
            activity_type="ai_answer_used",
            user_id=user_id,
            details={
                "anchor_document_id": anchor_document_id,
                "question_preview": question_preview[:400],
            },
        )
    audit_service.log_event(
        action="ai_answer_documents_used",
        user_id=user_id,
        role=role,
        document_id=anchor_document_id,
        details={
            "logical_document_ids": sorted(logical),
            "question_preview": question_preview[:400],
        },
    )


def split_answer_result(result: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Remove usage_document_ids before AnswerResponse validation."""
    payload = dict(result)
    raw = payload.pop("usage_document_ids", []) or []
    ids = [str(x) for x in raw if str(x).strip()]
    return payload, ids
