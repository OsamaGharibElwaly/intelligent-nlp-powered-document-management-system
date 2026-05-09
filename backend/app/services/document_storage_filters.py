"""Composable list filters for document productivity views (pure functions)."""

from datetime import UTC, date, datetime
from typing import Any


def _parse_iso_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    try:
        raw = str(value).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def apply_storage_filters(
    docs: list[dict[str, Any]],
    *,
    read_status: str | None = None,
    in_progress: bool | None = None,
    overdue: bool | None = None,
    priority: str | None = None,
    pinned_only: bool | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    out = list(docs)
    if not include_archived:
        out = [d for d in out if not bool(d.get("archived", False))]

    if read_status:
        rs = read_status.strip().lower()
        out = [d for d in out if str(d.get("read_status", "")).lower() == rs]

    if in_progress:
        filtered: list[dict[str, Any]] = []
        for d in out:
            st = str(d.get("read_status", "")).lower()
            prog = int(d.get("reading_progress", 0) or 0)
            if st == "reading":
                filtered.append(d)
            elif st != "completed" and 0 < prog < 100:
                filtered.append(d)
        out = filtered

    if overdue:
        today = datetime.now(UTC).date()
        filtered_o: list[dict[str, Any]] = []
        for d in out:
            if str(d.get("read_status", "")).lower() == "completed":
                continue
            dd = _parse_iso_date(str(d.get("due_date") or "") or None)
            if dd is not None and dd < today:
                filtered_o.append(d)
        out = filtered_o

    if priority:
        pr = priority.strip().lower()
        out = [d for d in out if str(d.get("priority", "")).lower() == pr]

    if pinned_only:
        out = [d for d in out if bool(d.get("pinned", False))]

    return out


def sort_documents(docs: list[dict[str, Any]], sort: str | None) -> list[dict[str, Any]]:
    if not sort:
        return docs
    key = sort.strip().lower()
    if key == "recently_read":

        def rr_key(d: dict[str, Any]) -> tuple[float, str]:
            dt = _parse_iso_dt(str(d.get("last_read_at") or "") or None)
            ts = dt.timestamp() if dt else 0.0
            return (-ts, str(d.get("document_id", "")))

        return sorted(docs, key=rr_key)
    if key == "due_date_asc":

        def due_key(d: dict[str, Any]) -> tuple[float, str]:
            dd = _parse_iso_date(str(d.get("due_date") or "") or None)
            # docs without due_date sort last
            order = dd.toordinal() if dd else 10**9
            return (order, str(d.get("document_id", "")))

        return sorted(docs, key=due_key)
    if key == "priority_desc":
        rank = {"high": 0, "medium": 1, "low": 2}

        def pr_key(d: dict[str, Any]) -> tuple[int, str]:
            p = str(d.get("priority", "medium")).lower()
            return (rank.get(p, 1), str(d.get("document_id", "")))

        return sorted(docs, key=pr_key)
    return docs
