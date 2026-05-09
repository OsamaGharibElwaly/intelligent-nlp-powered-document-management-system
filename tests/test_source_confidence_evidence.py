import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.qa import CONFIDENCE_FORMULA_VERSION
from app.services.rag_pipeline import (
    compute_answer_confidence,
    evidence_span_for_paragraph_chunk,
    pairwise_token_jaccard,
)


def test_evidence_span_prefers_full_paragraph_when_embedded() -> None:
    chunk = "Intro. FAISS stores vectors. Outro."
    span = evidence_span_for_paragraph_chunk("FAISS stores vectors.", chunk)
    assert span is not None
    start, end = span
    assert chunk[start:end] == "FAISS stores vectors."


def test_compute_confidence_is_deterministic_and_bounded() -> None:
    retrieved = [
        {"chunk_id": "a:0", "document_id": "d1", "chunk_text": "one two three", "relevance_score": 0.8},
        {"chunk_id": "a:1", "document_id": "d1", "chunk_text": "two three four", "relevance_score": 0.4},
    ]
    chunk_by_id = {str(r["chunk_id"]): r for r in retrieved}
    cites = [
        {
            "paragraph_index": 0,
            "citations": [
                {"chunk_id": "a:0", "document_id": "d1"},
                {"chunk_id": "a:1", "document_id": "d1"},
            ],
        }
    ]
    one = compute_answer_confidence(cites, retrieved, chunk_by_id)
    two = compute_answer_confidence(cites, retrieved, chunk_by_id)
    assert one == two
    assert 0.0 <= one["score"] <= 1.0
    assert one["supporting_unique_chunks"] == 2
    assert one["formula_version"] == CONFIDENCE_FORMULA_VERSION


def test_pairwise_jaccard_single_text() -> None:
    assert pairwise_token_jaccard(["only"]) == 1.0
