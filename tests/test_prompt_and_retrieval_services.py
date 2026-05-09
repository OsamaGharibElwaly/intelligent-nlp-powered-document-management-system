import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_engine import RetrievalEngine


class FakeEmbeddingService:
    async def embed_text(self, text: str) -> list[float]:
        if "alpha" in text.lower():
            return [1.0, 0.0]
        return [0.0, 1.0]


class FakeVectorStore:
    def list_chunks(self, document_ids: set[str] | None = None) -> list[dict[str, object]]:
        chunks = [
            {"document_id": "doc-1", "chunk_id": "doc-1:1", "order": 1, "text": "later alpha chunk"},
            {"document_id": "doc-1", "chunk_id": "doc-1:0", "order": 0, "text": "best alpha chunk"},
            {"document_id": "doc-2", "chunk_id": "doc-2:0", "order": 0, "text": "other doc"},
        ]
        if document_ids is not None:
            chunks = [item for item in chunks if str(item["document_id"]) in document_ids]
        return chunks

    async def search(self, embedding: list[float], top_k: int = 5, document_ids: set[str] | None = None) -> list[dict[str, object]]:
        return [
            {"document_id": "doc-1", "chunk_id": "doc-1:1", "order": 1, "text": "later chunk", "score": 0.7},
            {"document_id": "doc-1", "chunk_id": "doc-1:0", "order": 0, "text": "best chunk", "score": 0.7},
            {"document_id": "doc-2", "chunk_id": "doc-2:0", "order": 0, "text": "other doc", "score": 0.99},
        ][:top_k if document_ids is None else 3]


def test_prompt_builder_formats_context_and_question() -> None:
    builder = PromptBuilder()
    chunks = [
        {"chunk_id": "doc:0", "document_id": "logical-doc", "chunk_text": "Chunk one text"},
        {"chunk_id": "doc:1", "document_id": "logical-doc", "chunk_text": "Chunk two text"},
    ]
    system_prompt, user_prompt = builder.build_answer(
        "What is stored?",
        chunks,
        answer_mode="flexible",
        answer_length="medium",
    )

    assert "grounded qa system" in system_prompt.lower()
    assert "CONTEXT:" in user_prompt
    assert "[chunk_id=doc:0 document_id=logical-doc]" in user_prompt
    assert "Chunk one text" in user_prompt
    assert "QUESTION:" in user_prompt
    assert "What is stored?" in user_prompt
    assert "paragraphs" in user_prompt


def test_retrieval_engine_filters_and_sorts_results() -> None:
    engine = RetrievalEngine(embedding_service=FakeEmbeddingService(), vector_store=FakeVectorStore())  # type: ignore[arg-type]
    results = asyncio.run(engine.retrieve(query="alpha", document_id="doc-1", top_k=2))

    assert len(results) == 2
    assert results[0]["chunk_id"] == "doc-1:0"
    assert results[1]["chunk_id"] == "doc-1:1"
    assert results[0]["document_id"] == "doc-1"
