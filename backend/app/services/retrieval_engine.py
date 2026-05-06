from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


class RetrievalEngine:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def retrieve(self, query: str, document_id: str, top_k: int) -> list[dict[str, object]]:
        query_embedding = await self.embedding_service.embed_text(query)
        raw_results = await self.vector_store.search(embedding=query_embedding, top_k=top_k * 3)

        filtered = [item for item in raw_results if item.get("document_id") == document_id]
        filtered.sort(key=lambda item: (-float(item["score"]), int(item["order"])))

        return [
            {"chunk_id": str(item["chunk_id"]), "text": str(item["text"]), "score": float(item["score"])}
            for item in filtered[:top_k]
        ]
