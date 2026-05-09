from typing import Any

from pydantic import BaseModel, Field


class ErrorIntelEntryResponse(BaseModel):
    request_id: str
    timestamp: str
    error_type: str = Field(description="retrieval | llm | validation | system")
    severity: str = Field(description="info | warning | error | critical")
    endpoint: str
    message: str
    stack_trace: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
