from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


_LEARN_CHUNK_STEP = 0.02
_CHUNK_DELTA_CAP = 0.15
_KEYWORD_FLOOR = 0.30
_KEYWORD_CEIL = 0.75
_VEC_FLOOR = 0.25
_VEC_CEIL = 0.75


class LearningSignalsStore:
    """Persisted signals that affect only future retrievals (never past answers)."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "learning_signals.json"
        self._lock = Lock()

    def _default_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "chunk_relevance_delta": {},
            "hybrid_keyword_weight": 0.65,
            "hybrid_vector_weight": 0.35,
            "reindex_queue": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            data = self._default_payload()
            self._save(data)
            return dict(data)
        raw = self._path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        base = self._default_payload()
        base.update(parsed)
        deltas = parsed.get("chunk_relevance_delta")
        base["chunk_relevance_delta"] = dict(deltas) if isinstance(deltas, dict) else {}
        rq = parsed.get("reindex_queue")
        base["reindex_queue"] = list(rq) if isinstance(rq, list) else []
        kw = float(base.get("hybrid_keyword_weight", 0.65))
        vw = float(base.get("hybrid_vector_weight", 0.35))
        kw, vw = _normalize_hybrid_pair(kw, vw)
        base["hybrid_keyword_weight"] = kw
        base["hybrid_vector_weight"] = vw
        return base

    def _save(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._load())

    def get_chunk_delta(self, chunk_id: str) -> float:
        with self._lock:
            data = self._load()
            raw = data["chunk_relevance_delta"].get(str(chunk_id), 0.0)
            return float(raw)

    def get_hybrid_weights(self) -> tuple[float, float]:
        with self._lock:
            data = self._load()
            kw = float(data["hybrid_keyword_weight"])
            vw = float(data["hybrid_vector_weight"])
            return _normalize_hybrid_pair(kw, vw)

    def apply_feedback_to_chunks(self, chunk_ids: list[str], *, positive: bool) -> None:
        if not chunk_ids:
            return
        step = _LEARN_CHUNK_STEP if positive else -_LEARN_CHUNK_STEP
        with self._lock:
            data = self._load()
            deltas: dict[str, float] = dict(data["chunk_relevance_delta"])
            for cid in chunk_ids:
                key = str(cid)
                new_val = float(deltas.get(key, 0.0)) + step
                new_val = max(-_CHUNK_DELTA_CAP, min(_CHUNK_DELTA_CAP, new_val))
                if abs(new_val) < 1e-9:
                    deltas.pop(key, None)
                else:
                    deltas[key] = new_val
            data["chunk_relevance_delta"] = deltas
            self._save(data)

    def nudge_hybrid_weights(self, *, positive: bool) -> None:
        """Negative feedback biases slightly toward keyword; positive slightly toward vector."""
        with self._lock:
            data = self._load()
            kw = float(data["hybrid_keyword_weight"])
            vw = float(data["hybrid_vector_weight"])
            if positive:
                kw -= 0.005
                vw += 0.005
            else:
                kw += 0.005
                vw -= 0.005
            kw = max(_KEYWORD_FLOOR, min(_KEYWORD_CEIL, kw))
            vw = max(_VEC_FLOOR, min(_VEC_CEIL, vw))
            kw, vw = _normalize_hybrid_pair(kw, vw)
            data["hybrid_keyword_weight"] = kw
            data["hybrid_vector_weight"] = vw
            self._save(data)

    def flag_reindex(self, logical_document_id: str, reason: str) -> None:
        entry = {
            "logical_document_id": str(logical_document_id),
            "reason": str(reason),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            data = self._load()
            queue: list[Any] = list(data.get("reindex_queue", []))
            queue.append(entry)
            data["reindex_queue"] = queue[-500:]
            self._save(data)


def _normalize_hybrid_pair(keyword_w: float, vector_w: float) -> tuple[float, float]:
    total = keyword_w + vector_w
    if total <= 0:
        return 0.65, 0.35
    return keyword_w / total, vector_w / total
