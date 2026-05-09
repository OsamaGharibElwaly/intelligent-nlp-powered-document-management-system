import re
from typing import Any

from app.services.embedding_service import EmbeddingService
from app.services.learning_signals_store import LearningSignalsStore
from app.services.retrieval_storage_bias import storage_retrieval_multiplier
from app.services.vector_store import VectorStore


class RetrievalEngine:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        learning_signals: LearningSignalsStore | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self._learning = learning_signals

    def _normalize(self, values: dict[str, float]) -> dict[str, float]:
        if not values:
            return {}
        min_value = min(values.values())
        max_value = max(values.values())
        if max_value == min_value:
            return {key: 1.0 for key in values}
        scale = max_value - min_value
        return {key: (value - min_value) / scale for key, value in values.items()}

    def _keyword_stats(self, query: str, text: str) -> tuple[float, bool]:
        query_lc = query.strip().lower()
        text_lc = text.lower()
        has_exact_phrase = bool(query_lc) and query_lc in text_lc
        terms = re.findall(r"[a-zA-Z0-9]+", query_lc)
        term_hits = sum(text_lc.count(term) for term in terms if term)
        raw_score = float(term_hits + (3 if has_exact_phrase else 0))
        return raw_score, has_exact_phrase

    async def retrieve(
        self,
        query: str,
        document_id: str | None = None,
        top_k: int = 5,
        retrieval_mode: str = "hybrid",
        metadata_by_index_document_id: dict[str, dict[str, object]] | None = None,
    ) -> tuple[list[dict[str, object]], dict[str, Any]]:
        requested_mode = retrieval_mode.strip().lower()
        if requested_mode not in {"hybrid", "keyword", "vector"}:
            raise ValueError("Invalid retrieval mode. Allowed: hybrid, keyword, vector.")

        target_document_ids: set[str] | None = None
        if metadata_by_index_document_id:
            target_document_ids = set(metadata_by_index_document_id.keys())
        elif document_id:
            target_document_ids = {document_id}

        chunks = self.vector_store.list_chunks(document_ids=target_document_ids)
        if not chunks:
            return [], {"embedding_skipped": False, "vector_unavailable": False}

        retrieval_flags: dict[str, Any] = {"embedding_skipped": False, "vector_unavailable": False}

        query_embedding: list[float] | None = None
        vector_scores: dict[str, float] = {}
        if requested_mode in {"hybrid", "vector"}:
            try:
                query_embedding = await self.embedding_service.embed_text(query)
                semantic_results = await self.vector_store.search(
                    embedding=query_embedding,
                    top_k=max(top_k * 10, 50),
                    document_ids=target_document_ids,
                )
                vector_scores = {str(item["chunk_id"]): float(item.get("score", 0.0)) for item in semantic_results}
            except Exception:
                retrieval_flags["embedding_skipped"] = True
                vector_scores = {}
                query_embedding = None
                if requested_mode == "vector":
                    retrieval_flags["vector_unavailable"] = True
                    return [], retrieval_flags

        keyword_scores_raw: dict[str, float] = {}
        exact_match_by_chunk: dict[str, bool] = {}
        if requested_mode in {"hybrid", "keyword"}:
            for chunk in chunks:
                chunk_id = str(chunk.get("chunk_id", ""))
                score, has_exact = self._keyword_stats(query=query, text=str(chunk.get("text", "")))
                keyword_scores_raw[chunk_id] = score
                exact_match_by_chunk[chunk_id] = has_exact

        keyword_scores = self._normalize(keyword_scores_raw) if keyword_scores_raw else {}
        vector_scores_normalized = self._normalize(vector_scores) if vector_scores else {}

        ranked: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            base_document_id = str(chunk.get("document_id", ""))
            doc_metadata = (metadata_by_index_document_id or {}).get(base_document_id, {})
            logical_document_id = str(doc_metadata.get("document_id", base_document_id))

            keyword_score = keyword_scores.get(chunk_id, 0.0)
            vector_score = vector_scores_normalized.get(chunk_id, 0.0)
            has_exact_keyword = exact_match_by_chunk.get(chunk_id, False)
            if requested_mode == "keyword":
                relevance = keyword_score
            elif requested_mode == "vector":
                relevance = vector_score
            else:
                kw_w, vec_w = (0.65, 0.35)
                if self._learning is not None:
                    kw_w, vec_w = self._learning.get_hybrid_weights()
                relevance = (kw_w * keyword_score) + (vec_w * vector_score)

            delta = self._learning.get_chunk_delta(chunk_id) if self._learning is not None else 0.0
            storage_mult = storage_retrieval_multiplier(doc_metadata)
            relevance_adjusted = (float(relevance) + float(delta)) * storage_mult

            ranked.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": logical_document_id,
                    "chunk_text": str(chunk.get("text", "")),
                    "relevance_score": float(relevance_adjusted),
                    "metadata": {
                        "document": logical_document_id,
                        "tags": doc_metadata.get("tags", []),
                        "date": doc_metadata.get("date"),
                        "author": doc_metadata.get("author"),
                        "storage_bias_multiplier": storage_mult,
                    },
                    "_exact": has_exact_keyword,
                    "_keyword_raw": keyword_scores_raw.get(chunk_id, 0.0),
                    "_vector_raw": vector_scores.get(chunk_id, 0.0),
                    "_order": int(chunk.get("order", 0)),
                }
            )

        if requested_mode == "keyword":
            ranked = [item for item in ranked if float(item["_keyword_raw"]) > 0]
        if requested_mode == "vector":
            ranked = [item for item in ranked if str(item["chunk_id"]) in vector_scores]

        ranked.sort(
            key=lambda item: (
                not bool(item["_exact"]),
                -float(item["relevance_score"]),  # includes learned chunk delta
                -float(item["_keyword_raw"]),
                -float(item["_vector_raw"]),
                int(item["_order"]),
                str(item["chunk_id"]),
            )
        )

        cleaned: list[dict[str, object]] = []
        for item in ranked[:top_k]:
            md = dict(item["metadata"])
            if retrieval_flags.get("embedding_skipped"):
                md = {**md, "keyword_only_fallback": True}
            cleaned.append(
                {
                    "chunk_id": str(item["chunk_id"]),
                    "document_id": str(item["document_id"]),
                    "chunk_text": str(item["chunk_text"]),
                    "relevance_score": float(item["relevance_score"]),
                    "metadata": md,
                }
            )
        return cleaned, retrieval_flags
