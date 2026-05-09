import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class DocumentActivityStore:
    """Append-only per-document activity timelines (file-backed, migration-safe)."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "document_activity.json"
        self._lock = Lock()
        if not self._path.exists():
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        raw = self._path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        out: dict[str, list[dict[str, Any]]] = {}
        for doc_id, entries in parsed.items():
            if not isinstance(entries, list):
                continue
            cleaned: list[dict[str, Any]] = []
            for item in entries:
                if isinstance(item, dict):
                    cleaned.append(dict(item))
            out[str(doc_id)] = cleaned
        return out

    def _save(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def append(
        self,
        *,
        document_id: str,
        activity_type: str,
        user_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "activity_id": str(uuid.uuid4()),
            "document_id": document_id,
            "activity_type": activity_type.strip().lower(),
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "details": dict(details or {}),
        }
        with self._lock:
            data = self._load()
            bucket = list(data.get(document_id, []))
            bucket.append(entry)
            data[document_id] = bucket
            self._save(data)
        return entry

    def list_for_document(
        self,
        document_id: str,
        *,
        activity_type: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._load().get(document_id, []))
        ordered = sorted(entries, key=lambda e: str(e.get("timestamp", "")))
        if activity_type:
            at = activity_type.strip().lower()
            ordered = [e for e in ordered if str(e.get("activity_type", "")).lower() == at]
        return ordered[-limit:]
