from typing import Literal

from pydantic import BaseModel, Field


FeedbackSentiment = Literal["positive", "negative"]


class RetrievedChunkSnapshot(BaseModel):
    chunk_id: str = Field(min_length=1)
    relevance_score: float | None = None


class FeedbackRequest(BaseModel):
    sentiment: FeedbackSentiment
    query: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    answer: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieved_chunks: list[RetrievedChunkSnapshot] = Field(default_factory=list)
    interaction_id: str | None = Field(default=None, min_length=1)


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str = "recorded"
