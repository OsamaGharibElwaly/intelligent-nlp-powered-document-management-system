"""Emit notifications for collaboration + AI events (Phase 4.2)."""

import logging
from collections.abc import Callable
from typing import Any

from app.services.document_repository import DocumentRepository
from app.services.notification_store import NotificationStore
from app.services.workspace_store import WorkspaceStore

_logger = logging.getLogger(__name__)


def _emit_guard(stage: str, work: Callable[[], None]) -> None:
    try:
        work()
    except Exception:
        _logger.exception("notification_emit_failed stage=%s", stage)


def _collaborator_emails(
    *,
    document_repository: DocumentRepository,
    workspace_store: WorkspaceStore,
    document_id: str,
    exclude: set[str] | None = None,
) -> list[str]:
    exclude_l = {e.strip().lower() for e in (exclude or set()) if str(e).strip()}
    doc = document_repository.get(document_id.strip())
    if doc is None:
        return []
    emails: set[str] = {str(doc.get("owner_id", "")).strip().lower()}
    wid = doc.get("workspace_id")
    if wid and str(wid).strip():
        ws = workspace_store.get(str(wid).strip())
        if ws:
            emails.add(str(ws.get("owner_id", "")).strip().lower())
            for m in ws.get("members", {}) or {}:
                emails.add(str(m).strip().lower())
    emails.discard("")
    return sorted(e for e in emails if e and e not in exclude_l)


def _doc_link(document_id: str, *, panel: str, thread_id: str | None = None) -> dict[str, Any]:
    link: dict[str, Any] = {"document_id": document_id.strip(), "panel": panel}
    if thread_id and str(thread_id).strip():
        link["thread_id"] = str(thread_id).strip()
    return link


def notify_document_updated(
    *,
    notification_store: NotificationStore,
    document_repository: DocumentRepository,
    workspace_store: WorkspaceStore,
    actor_email: str,
    document_id: str,
    summary: str,
) -> None:
    def _work() -> None:
        recipients = _collaborator_emails(
            document_repository=document_repository,
            workspace_store=workspace_store,
            document_id=document_id,
            exclude={actor_email},
        )
        if not recipients:
            return
        notification_store.append_for_users(
            recipients,
            type_="info",
            category="document_updated",
            title="Document updated",
            body=summary[:2000],
            link=_doc_link(document_id, panel="documents"),
        )

    _emit_guard("document_updated", _work)


def notify_reindexed(
    *,
    notification_store: NotificationStore,
    document_repository: DocumentRepository,
    workspace_store: WorkspaceStore,
    actor_email: str,
    document_id: str,
    context: str,
) -> None:
    def _work() -> None:
        recipients = _collaborator_emails(
            document_repository=document_repository,
            workspace_store=workspace_store,
            document_id=document_id,
            exclude={actor_email},
        )
        if not recipients:
            return
        notification_store.append_for_users(
            recipients,
            type_="success",
            category="document_reindexed",
            title="Document re-indexed",
            body=context[:2000],
            link=_doc_link(document_id, panel="documents"),
        )

    _emit_guard("reindexed", _work)


def notify_ai_answer(
    *,
    notification_store: NotificationStore,
    document_repository: DocumentRepository,
    workspace_store: WorkspaceStore,
    actor_email: str,
    document_id: str,
    thread_id: str | None,
    question_preview: str,
) -> None:
    def _work() -> None:
        recipients = _collaborator_emails(
            document_repository=document_repository,
            workspace_store=workspace_store,
            document_id=document_id,
            exclude={actor_email},
        )
        if not recipients:
            return
        preview = question_preview.strip()[:280]
        notification_store.append_for_users(
            recipients,
            type_="success",
            category="ai_answer",
            title="New AI answer",
            body=preview,
            link=_doc_link(document_id, panel="query", thread_id=thread_id),
        )

    _emit_guard("ai_answer", _work)


def notify_query_failed(
    *,
    notification_store: NotificationStore,
    user_email: str,
    document_id: str,
    detail: str,
) -> None:
    def _work() -> None:
        notification_store.append_for_user(
            user_id=user_email,
            type_="error",
            category="query_failed",
            title="Query failed",
            body=str(detail).strip()[:2000],
            link=_doc_link(document_id, panel="query"),
        )

    _emit_guard("query_failed", _work)


def notify_new_comment(
    *,
    notification_store: NotificationStore,
    document_repository: DocumentRepository,
    workspace_store: WorkspaceStore,
    actor_email: str,
    document_id: str,
    thread_id: str | None,
    preview: str,
) -> None:
    def _work() -> None:
        recipients = _collaborator_emails(
            document_repository=document_repository,
            workspace_store=workspace_store,
            document_id=document_id,
            exclude={actor_email},
        )
        if not recipients:
            return
        notification_store.append_for_users(
            recipients,
            type_="info",
            category="comment",
            title="New comment",
            body=preview.strip()[:2000],
            link=_doc_link(document_id, panel="query", thread_id=thread_id),
        )

    _emit_guard("new_comment", _work)
