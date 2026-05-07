import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class AuditService:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._log_file = self._root / "audit.log"
        self._lock = Lock()
        if not self._log_file.exists():
            self._log_file.touch()

    def log_event(
        self,
        *,
        action: str,
        user_id: str,
        role: str,
        document_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "user_id": user_id,
            "role": role,
            "document_id": document_id,
            "details": details or {},
        }
        line = json.dumps(entry, ensure_ascii=True)
        with self._lock:
            with self._log_file.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")

    def _read_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        if not self._log_file.exists():
            return entries
        with self._log_file.open("r", encoding="utf-8") as fp:
            for raw in fp:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
        return entries

    def list_events(
        self,
        *,
        user_id: str | None = None,
        action: str | None = None,
        document_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        entries = self._read_entries()
        filtered = entries
        if user_id:
            filtered = [entry for entry in filtered if str(entry.get("user_id", "")) == user_id]
        if action:
            filtered = [entry for entry in filtered if str(entry.get("action", "")) == action]
        if document_id:
            filtered = [entry for entry in filtered if str(entry.get("document_id", "")) == document_id]
        return filtered[-limit:]

    def last_accessed_documents(self, user_id: str, limit: int = 20) -> list[str]:
        entries = self.list_events(user_id=user_id, action="document_access", limit=1000)
        seen: set[str] = set()
        ordered: list[str] = []
        for entry in reversed(entries):
            doc_id = str(entry.get("document_id", "")).strip()
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            ordered.append(doc_id)
            if len(ordered) >= limit:
                break
        return ordered
