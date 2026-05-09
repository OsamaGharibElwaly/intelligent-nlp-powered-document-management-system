import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rag_pipeline import RAGPipelineService


def test_enforce_strict_replaces_non_verbatim_with_chunk_excerpt() -> None:
    pipeline = RAGPipelineService(retrieval_engine=None, prompt_builder=None, llm_service=None)  # type: ignore[arg-type]
    chunk_by_id = {
        "d:0": {"chunk_id": "d:0", "document_id": "logical", "chunk_text": "Known fact alpha beta gamma."},
    }
    citations = [{"chunk_id": "d:0", "document_id": "logical"}]
    fixed = pipeline._enforce_strict_paragraph("Totally unrelated paragraph.", citations, chunk_by_id)
    assert fixed == "Known fact alpha beta gamma."
