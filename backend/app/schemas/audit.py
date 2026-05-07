from pydantic import BaseModel


class AuditLogEntryResponse(BaseModel):
    timestamp: str
    action: str
    user_id: str
    role: str
    document_id: str | None = None
    details: dict[str, object]


class UsageHistoryResponse(BaseModel):
    user_id: str
    query_history: list[AuditLogEntryResponse]
    last_accessed_documents: list[str]
