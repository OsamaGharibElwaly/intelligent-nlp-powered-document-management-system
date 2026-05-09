from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalFilters

AnswerMode = Literal["strict", "flexible"]
AnswerLength = Literal["short", "medium", "detailed"]

CONFIDENCE_FORMULA_VERSION = "2.3.0-v1"


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_ids: list[str] | None = None
    filters: RetrievalFilters | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    retrieval_mode: str = Field(default="hybrid")
    answer_mode: AnswerMode = "flexible"
    answer_length: AnswerLength = "medium"


class SourceCitation(BaseModel):
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)


class ParagraphCitationBlock(BaseModel):
    paragraph_index: int = Field(ge=0)
    citations: list[SourceCitation] = Field(min_length=1)


class AnswerConfidence(BaseModel):
    """Reproducible aggregate confidence from retrieval overlap (Phase 2.3)."""

    score: float = Field(ge=0.0, le=1.0)
    formula_version: str = CONFIDENCE_FORMULA_VERSION
    supporting_unique_chunks: int = Field(ge=0)
    support_component: float = Field(ge=0.0, le=1.0)
    relevance_component: float = Field(ge=0.0, le=1.0)
    agreement_component: float = Field(ge=0.0, le=1.0)
    relevance_mean_raw: float
    max_retrieval_score_raw: float


class EvidenceSpan(BaseModel):
    """Verbatim slice of chunk text at [span_start:span_end); chunk storage is never mutated."""

    paragraph_index: int = Field(ge=0)
    chunk_id: str
    document_id: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    span_text: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[ParagraphCitationBlock]
    confidence: AnswerConfidence
    evidence_spans: list[EvidenceSpan]
    degraded: bool = False
    degraded_reason: str | None = None
    llm_attempts: int | None = None
    retrieval_degraded: bool = False
