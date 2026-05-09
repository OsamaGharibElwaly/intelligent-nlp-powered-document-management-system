import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal

ErrorCategory = Literal["retrieval", "llm", "validation", "system"]
Severity = Literal["info", "warning", "error", "critical"]

_MAX_FILE_LINES = 4000
_KEEP_AFTER_COMPACT = 2500


class ErrorIntelligenceStore:
    """Append-only JSONL store for classified errors (admin-facing intelligence layer)."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._log_file = self._root / "error_intelligence.log"
        self._lock = Lock()
        if not self._log_file.exists():
            self._log_file.touch()

    def _compact_if_needed(self) -> None:
        try:
            lines = self._log_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= _MAX_FILE_LINES:
            return
        keep = lines[-_KEEP_AFTER_COMPACT:]
        tmp = self._log_file.with_suffix(".log.tmp")
        tmp.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
        tmp.replace(self._log_file)

    def record(
        self,
        *,
        error_type: ErrorCategory,
        severity: Severity,
        endpoint: str,
        message: str,
        request_id: str | None = None,
        stack_trace: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        rid = request_id or str(uuid.uuid4())
        entry = {
            "request_id": rid,
            "timestamp": datetime.now(UTC).isoformat(),
            "error_type": error_type,
            "severity": severity,
            "endpoint": endpoint,
            "message": message[:8000],
            "stack_trace": stack_trace[:32000] if stack_trace else None,
            "extra": extra or {},
        }
        line = json.dumps(entry, ensure_ascii=True)
        with self._lock:
            with self._log_file.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
            self._compact_if_needed()
        return rid

    def list_events(
        self,
        *,
        endpoint_prefix: str | None = None,
        severity: str | None = None,
        error_type: str | None = None,
        since_iso: str | None = None,
        until_iso: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        entries = self._read_all()
        since_ts = _parse_iso(since_iso) if since_iso else None
        until_ts = _parse_iso(until_iso) if until_iso else None

        filtered: list[dict[str, Any]] = []
        for entry in entries:
            if endpoint_prefix and not str(entry.get("endpoint", "")).startswith(endpoint_prefix):
                continue
            if severity and str(entry.get("severity", "")) != severity:
                continue
            if error_type and str(entry.get("error_type", "")) != error_type:
                continue
            ts = _parse_iso(str(entry.get("timestamp", "")))
            if since_ts is not None and ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts is not None and ts > until_ts:
                continue
            filtered.append(entry)

        filtered.sort(key=lambda e: str(e.get("timestamp", "")), reverse=True)
        return filtered[:limit]

    def _read_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self._log_file.exists():
            return out
        with self._lock:
            try:
                raw_lines = self._log_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                return out
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                out.append(parsed)
        return out


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
