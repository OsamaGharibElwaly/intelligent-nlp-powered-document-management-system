import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._model = SentenceTransformer(self.MODEL_NAME)

    async def embed_text(self, text: str) -> list[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned_texts = [text.strip() for text in texts if text.strip()]
        if not cleaned_texts:
            return []

        vectors = self._model.encode(cleaned_texts, convert_to_numpy=True, normalize_embeddings=False)
        normalized_vectors = self._normalize(vectors)
        return normalized_vectors.tolist()

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        safe_norms = np.where(norms == 0, 1.0, norms)
        return vectors / safe_norms
