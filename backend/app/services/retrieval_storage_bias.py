"""Retrieval score adjustments from document storage state (AI/RAG integration boundary)."""

from typing import Any


def storage_retrieval_multiplier(metadata: dict[str, Any]) -> float:
    """Prefer unread/in-progress; down-rank archived and completed slightly."""
    mult = 1.0
    if bool(metadata.get("archived")):
        mult *= 0.35
    rs = str(metadata.get("read_status", "unread")).lower()
    if rs == "unread":
        mult *= 1.15
    elif rs == "reading":
        mult *= 1.10
    elif rs == "completed":
        mult *= 0.95
    pr = str(metadata.get("priority", "medium")).lower()
    if pr == "high":
        mult *= 1.08
    elif pr == "low":
        mult *= 0.97
    return float(mult)
