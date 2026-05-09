from app.services.retrieval_engine import RetrievalEngine


class RetrieveChunksUseCase:
    def __init__(self, retrieval_engine: RetrievalEngine) -> None:
        self.retrieval_engine = retrieval_engine

    async def execute(
        self,
        query: str,
        document_id: str | None,
        top_k: int,
        retrieval_mode: str = "hybrid",
        metadata_by_index_document_id: dict[str, dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        rows, _flags = await self.retrieval_engine.retrieve(
            query=query,
            document_id=document_id,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            metadata_by_index_document_id=metadata_by_index_document_id,
        )
        return rows
