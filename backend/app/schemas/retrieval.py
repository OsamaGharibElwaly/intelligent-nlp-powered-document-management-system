from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class RetrievalItem(BaseModel):
    chunk_id: str
    text: str
    score: float
