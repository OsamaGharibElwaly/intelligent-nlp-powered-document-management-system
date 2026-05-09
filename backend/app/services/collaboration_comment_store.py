"""Comments on AI answers / documents (Phase 4.1)."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class CollaborationCommentStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "collaboration_comments.json"
        self._lock = Lock()
        if not self._path.exists():
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, dict[str, Any]]:
        raw = self._path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(k): dict(v) for k, v in parsed.items() if isinstance(v, dict)}

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_for_thread(self, thread_id: str) -> list[dict[str, Any]]:
        tid = thread_id.strip()
        with self._lock:
            data = self._load()
        rows = [dict(r) for r in data.values() if str(r.get("thread_id", "")) == tid]
        return sorted(rows, key=lambda r: str(r.get("created_at", "")))

    def list_for_document(self, document_id: str) -> list[dict[str, Any]]:
        did = document_id.strip()
        with self._lock:
            data = self._load()
        rows = [dict(r) for r in data.values() if str(r.get("document_id", "")) == did and not str(r.get("thread_id", ""))]
        return sorted(rows, key=lambda r: str(r.get("created_at", "")))

    def create(
        self,
        *,
        user_id: str,
        document_id: str,
        body: str,
        thread_id: str | None = None,
        answer_anchor: str | None = None,
    ) -> dict[str, Any]:
        body_clean = str(body).strip()
        if not body_clean:
            raise ValueError("Comment body is required.")
        cid = str(uuid.uuid4())
        row: dict[str, Any] = {
            "comment_id": cid,
            "user_id": user_id.strip().lower(),
            "document_id": document_id.strip(),
            "thread_id": None if thread_id is None or str(thread_id).strip() == "" else str(thread_id).strip(),
            "answer_anchor": None if answer_anchor is None else str(answer_anchor).strip()[:120],
            "body": body_clean[:8000],
            "created_at": _iso_now(),
        }
        with self._lock:
            data = self._load()
            data[cid] = row
            self._save(data)
        return dict(row)
