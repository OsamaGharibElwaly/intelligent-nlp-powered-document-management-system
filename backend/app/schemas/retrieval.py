from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    tags: list[str] | None = None
    author: str | None = None


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    document_id: str | None = Field(default=None, min_length=1)
    document_ids: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    retrieval_mode: str = Field(default="hybrid")
    filters: RetrievalFilters | None = None


class RetrievalItem(BaseModel):
    chunk_id: str
    document_id: str
    chunk_text: str
    relevance_score: float
    metadata: dict[str, object]
