from typing import Any

import faiss
import numpy as np


class VectorStore:
    def __init__(self) -> None:
        self._index: faiss.IndexFlatIP | None = None
        self._metadata_by_position: dict[int, dict[str, Any]] = {}
        self._next_position = 0

    async def upsert(
        self,
        document_id: str,
        chunk_id: str,
        order: int,
        embedding: list[float],
        text: str,
    ) -> None:
        vector = np.asarray(embedding, dtype=np.float32)
        if vector.ndim != 1:
            raise ValueError("Embedding vector must be one-dimensional.")

        if self._index is None:
            self._index = faiss.IndexFlatIP(vector.shape[0])

        if vector.shape[0] != self._index.d:
            raise ValueError("Embedding dimension mismatch.")

        vector_2d = np.expand_dims(vector, axis=0)
        self._index.add(vector_2d)
        self._metadata_by_position[self._next_position] = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "order": order,
            "embedding": embedding,
            "text": text,
        }
        self._next_position += 1

    async def search(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if self._index is None or self._index.ntotal == 0:
            return []

        query_vector = np.asarray(embedding, dtype=np.float32)
        if query_vector.ndim != 1 or query_vector.shape[0] != self._index.d:
            raise ValueError("Invalid query embedding dimension.")

        query_2d = np.expand_dims(query_vector, axis=0)
        distances, indices = self._index.search(query_2d, min(top_k, self._index.ntotal))

        results: list[dict[str, Any]] = []
        for score, idx in zip(distances[0], indices[0], strict=False):
            if idx < 0:
                continue
            metadata = self._metadata_by_position.get(int(idx))
            if metadata is None:
                continue
            results.append({**metadata, "score": float(score)})
        return results
