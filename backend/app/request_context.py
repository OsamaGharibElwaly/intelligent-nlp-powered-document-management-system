"""Per-request context for correlating logs (async-task safe)."""

from typing import Any

from contextvars import ContextVar

current_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
current_request_path: ContextVar[str | None] = ContextVar("request_path", default=None)
current_request_metrics: ContextVar[dict[str, Any] | None] = ContextVar("request_metrics", default=None)
