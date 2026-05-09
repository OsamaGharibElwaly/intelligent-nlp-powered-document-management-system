"""Shared retrieval scope resolution for /retrieve and /query (Phase 2 integration)."""

from datetime import date
from typing import Any

from app.schemas.retrieval import RetrievalFilters


def matches_document_date_range(doc: dict[str, Any], from_date: date | None, to_date: date | None) -> bool:
    metadata = dict(doc.get("metadata", {}))
    date_value = str(metadata.get("date", "")).strip()
    if not date_value:
        return False
    try:
        candidate = date.fromisoformat(date_value)
    except ValueError:
        return False
    if from_date and candidate < from_date:
        return False
    if to_date and candidate > to_date:
        return False
    return True


def build_metadata_by_active_indexes(
    document_repository: Any,
    docs: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata_by_index_document_id: dict[str, dict[str, Any]] = {}
    for doc in docs:
        logical_id = str(doc.get("document_id", ""))
        active = document_repository.get_active_version(logical_id)
        index_document_id = str(active["index_document_id"])
        doc_metadata = dict(doc.get("metadata", {}))
        metadata_by_index_document_id[index_document_id] = {
            "document_id": logical_id,
            "tags": list(doc.get("tags", [])),
            "date": doc_metadata.get("date"),
            "author": doc_metadata.get("author"),
        }
    return metadata_by_index_document_id


def resolve_retrieval_documents(
    *,
    user: dict[str, object],
    document_repository: Any,
    document_id: str | None,
    document_ids: list[str] | None,
    filters: RetrievalFilters | None,
) -> list[dict[str, Any]]:
    """Apply RBAC + filters; matches legacy /retrieve narrowing semantics."""
    docs = document_repository.list_for_user(user)

    if document_id:
        document_repository.assert_access(user=user, document_id=document_id)
        docs = [doc for doc in docs if str(doc.get("document_id", "")) == document_id]

    if document_ids:
        allowed_ids = {doc_id for doc_id in document_ids if doc_id}
        for lid in sorted(allowed_ids):
            document_repository.assert_access(user=user, document_id=lid)
        docs = [doc for doc in docs if str(doc.get("document_id", "")) in allowed_ids]

    if filters:
        if filters.tags:
            required_tags = {tag.strip().lower() for tag in filters.tags if tag.strip()}
            docs = [
                doc
                for doc in docs
                if required_tags.issubset({str(tag).strip().lower() for tag in list(doc.get("tags", []))})
            ]
        if filters.author:
            expected_author = filters.author.strip().lower()
            docs = [
                doc
                for doc in docs
                if str(dict(doc.get("metadata", {})).get("author", "")).strip().lower() == expected_author
            ]
        if filters.date_from or filters.date_to:
            from_date = date.fromisoformat(filters.date_from) if filters.date_from else None
            to_date = date.fromisoformat(filters.date_to) if filters.date_to else None
            docs = [doc for doc in docs if matches_document_date_range(doc, from_date=from_date, to_date=to_date)]

    return docs


def resolve_query_documents(
    *,
    user: dict[str, object],
    document_repository: Any,
    anchor_document_id: str,
    document_ids: list[str] | None,
    filters: RetrievalFilters | None,
) -> list[dict[str, Any]]:
    """Resolve docs for /query: anchor doc required; optional multi-doc via document_ids."""
    document_repository.assert_access(user=user, document_id=anchor_document_id)

    docs = document_repository.list_for_user(user)

    if document_ids:
        allowed_ids = {doc_id for doc_id in document_ids if doc_id}
        if anchor_document_id not in allowed_ids:
            raise ValueError("document_id must be included in document_ids for multi-document queries.")
        for lid in sorted(allowed_ids):
            document_repository.assert_access(user=user, document_id=lid)
        docs = [doc for doc in docs if str(doc.get("document_id", "")) in allowed_ids]
    else:
        docs = [doc for doc in docs if str(doc.get("document_id", "")) == anchor_document_id]

    if filters:
        if filters.tags:
            required_tags = {tag.strip().lower() for tag in filters.tags if tag.strip()}
            docs = [
                doc
                for doc in docs
                if required_tags.issubset({str(tag).strip().lower() for tag in list(doc.get("tags", []))})
            ]
        if filters.author:
            expected_author = filters.author.strip().lower()
            docs = [
                doc
                for doc in docs
                if str(dict(doc.get("metadata", {})).get("author", "")).strip().lower() == expected_author
            ]
        if filters.date_from or filters.date_to:
            from_date = date.fromisoformat(filters.date_from) if filters.date_from else None
            to_date = date.fromisoformat(filters.date_to) if filters.date_to else None
            docs = [doc for doc in docs if matches_document_date_range(doc, from_date=from_date, to_date=to_date)]

    return docs
