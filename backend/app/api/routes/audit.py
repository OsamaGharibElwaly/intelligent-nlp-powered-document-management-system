from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.auth import require_roles
from app.dependencies import audit_service
from app.dependencies import error_intelligence_store
from app.dependencies import observability_metrics_store
from app.schemas.audit import AuditLogEntryResponse, UsageHistoryResponse
from app.schemas.error_intel import ErrorIntelEntryResponse

router = APIRouter(prefix="/audit", tags=["audit"])


def _metrics_range_bounds(range_key: Literal["24h", "7d", "30d"]) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    if range_key == "24h":
        delta = timedelta(hours=24)
    elif range_key == "7d":
        delta = timedelta(days=7)
    else:
        delta = timedelta(days=30)
    return now - delta, now


@router.get("/metrics/summary")
async def observability_metrics_summary(
    user: Annotated[dict[str, object], Depends(require_roles({"admin"}))],
    range_key: Literal["24h", "7d", "30d"] = Query("24h", alias="range"),
) -> dict[str, object]:
    _ = user
    return observability_metrics_store.summarize(range_key)


@router.get("/metrics/export")
async def observability_metrics_export(
    user: Annotated[dict[str, object], Depends(require_roles({"admin"}))],
    range_key: Literal["24h", "7d", "30d"] = Query("30d", alias="range"),
    format: Literal["json", "csv"] = Query("json"),
):
    _ = user
    since, until = _metrics_range_bounds(range_key)
    if format == "csv":
        body = observability_metrics_store.export_csv(since, until)
        return PlainTextResponse(
            body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="observability-metrics-{range_key}.csv"'},
        )
    rows = observability_metrics_store.events_in_range(since, until)
    return rows


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


@router.get("/error-events", response_model=list[ErrorIntelEntryResponse])
async def list_error_events(
    user: Annotated[dict[str, object], Depends(require_roles({"admin"}))],
    endpoint_prefix: str | None = Query(default=None, description="Filter by path prefix e.g. /query"),
    severity: str | None = Query(default=None, description="info | warning | error | critical"),
    error_type: str | None = Query(default=None, description="retrieval | llm | validation | system"),
    since: str | None = Query(default=None, description="ISO-8601 lower bound (inclusive)"),
    until: str | None = Query(default=None, description="ISO-8601 upper bound (inclusive)"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[ErrorIntelEntryResponse]:
    _ = user
    rows = error_intelligence_store.list_events(
        endpoint_prefix=endpoint_prefix,
        severity=severity,
        error_type=error_type,
        since_iso=since,
        until_iso=until,
        limit=limit,
    )
    return [ErrorIntelEntryResponse.model_validate(row) for row in rows]


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
