"""Shared query threads (Phase 4.1)."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class CollaborationThreadStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "collaboration_threads.json"
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

    def get(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._load().get(thread_id.strip())
        return dict(row) if row else None

    def list_for_document(self, document_id: str) -> list[dict[str, Any]]:
        did = document_id.strip()
        with self._lock:
            data = self._load()
        rows = [dict(r) for r in data.values() if str(r.get("document_id", "")) == did]
        return sorted(rows, key=lambda r: str(r.get("updated_at", "")), reverse=True)

    def create_thread(
        self,
        *,
        document_id: str,
        workspace_id: str | None,
        created_by: str,
        question: str,
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        tid = str(uuid.uuid4())
        now = _iso_now()
        wid = None if workspace_id is None or str(workspace_id).strip() == "" else str(workspace_id).strip()
        citations = answer_payload.get("citations") if isinstance(answer_payload.get("citations"), list) else []
        confidence = answer_payload.get("confidence") if isinstance(answer_payload.get("confidence"), dict) else {}
        evidence_spans = answer_payload.get("evidence_spans") if isinstance(answer_payload.get("evidence_spans"), list) else []
        ans = str(answer_payload.get("answer", ""))
        turn = {
            "turn_id": str(uuid.uuid4()),
            "created_at": now,
            "created_by": created_by.strip().lower(),
            "question": question.strip(),
            "answer": ans,
            "citations": citations,
            "confidence": confidence,
        }
        row: dict[str, Any] = {
            "thread_id": tid,
            "document_id": document_id.strip(),
            "workspace_id": wid,
            "created_by": created_by.strip().lower(),
            "created_at": now,
            "updated_at": now,
            "question": question.strip(),
            "answer": ans,
            "citations": citations,
            "confidence": confidence,
            "evidence_spans": evidence_spans,
            "turns": [turn],
            "discussion": [],
        }
        with self._lock:
            data = self._load()
            data[tid] = row
            self._save(data)
        return dict(row)

    def append_turn(
        self,
        thread_id: str,
        *,
        created_by: str,
        question: str,
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = _iso_now()
        turn = {
            "turn_id": str(uuid.uuid4()),
            "created_at": now,
            "created_by": created_by.strip().lower(),
            "question": question.strip(),
            "answer": str(answer_payload.get("answer", "")),
            "citations": answer_payload.get("citations") if isinstance(answer_payload.get("citations"), list) else [],
            "confidence": answer_payload.get("confidence") if isinstance(answer_payload.get("confidence"), dict) else {},
        }
        with self._lock:
            data = self._load()
            row = data.get(thread_id.strip())
            if row is None:
                raise ValueError("Thread not found.")
            row = dict(row)
            turns = list(row.get("turns", []))
            turns.append(turn)
            row["turns"] = turns
            row["question"] = question.strip()
            row["answer"] = turn["answer"]
            row["citations"] = turn["citations"]
            row["confidence"] = turn["confidence"]
            row["evidence_spans"] = answer_payload.get("evidence_spans")
            if isinstance(row["evidence_spans"], list):
                pass
            else:
                row["evidence_spans"] = []
            row["updated_at"] = now
            data[thread_id.strip()] = row
            self._save(data)
        return dict(row)

    def append_discussion(self, thread_id: str, *, user_id: str, body: str) -> dict[str, Any]:
        body_clean = str(body).strip()
        if not body_clean:
            raise ValueError("Message body is required.")
        msg = {
            "message_id": str(uuid.uuid4()),
            "user_id": user_id.strip().lower(),
            "body": body_clean[:8000],
            "created_at": _iso_now(),
        }
        with self._lock:
            data = self._load()
            row = data.get(thread_id.strip())
            if row is None:
                raise ValueError("Thread not found.")
            row = dict(row)
            disc = list(row.get("discussion", []))
            disc.append(msg)
            row["discussion"] = disc
            row["updated_at"] = msg["created_at"]
            data[thread_id.strip()] = row
            self._save(data)
        return dict(row)
