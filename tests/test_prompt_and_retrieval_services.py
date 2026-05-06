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
    async def search(self, embedding: list[float], top_k: int = 5) -> list[dict[str, object]]:
        return [
            {"document_id": "doc-1", "chunk_id": "doc-1:1", "order": 1, "text": "later chunk", "score": 0.7},
            {"document_id": "doc-1", "chunk_id": "doc-1:0", "order": 0, "text": "best chunk", "score": 0.7},
            {"document_id": "doc-2", "chunk_id": "doc-2:0", "order": 0, "text": "other doc", "score": 0.99},
        ][:top_k]


def test_prompt_builder_formats_context_and_question() -> None:
    builder = PromptBuilder()
    system_prompt, user_prompt = builder.build("What is stored?", ["Chunk one text", "Chunk two text"])

    assert "grounded QA system" in system_prompt
    assert "CONTEXT:" in user_prompt
    assert "[Chunk 1]" in user_prompt
    assert "QUESTION:" in user_prompt
    assert "What is stored?" in user_prompt


def test_retrieval_engine_filters_and_sorts_results() -> None:
    engine = RetrievalEngine(embedding_service=FakeEmbeddingService(), vector_store=FakeVectorStore())  # type: ignore[arg-type]
    results = asyncio.run(engine.retrieve(query="alpha", document_id="doc-1", top_k=2))

    assert len(results) == 2
    assert results[0]["chunk_id"] == "doc-1:0"
    assert results[1]["chunk_id"] == "doc-1:1"
