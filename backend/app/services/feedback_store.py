from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


class FeedbackStore:
    """Append-only feedback log linked to queries, chunks, and answers (snapshots only)."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "feedback.jsonl"
        self._lock = Lock()
        if not self._path.exists():
            self._path.touch()

    def append(self, record: dict[str, Any]) -> str:
        feedback_id = str(record.get("feedback_id") or uuid.uuid4())
        payload = {**record, "feedback_id": feedback_id, "stored_at": datetime.now(UTC).isoformat()}
        line = json.dumps(payload, ensure_ascii=True)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        return feedback_id

    def list_recent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._path.exists():
            return rows
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        for raw in lines[-limit:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows
