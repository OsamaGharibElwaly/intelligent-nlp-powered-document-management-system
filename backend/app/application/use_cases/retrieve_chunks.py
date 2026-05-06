from app.services.retrieval_engine import RetrievalEngine


class RetrieveChunksUseCase:
    def __init__(self, retrieval_engine: RetrievalEngine) -> None:
        self.retrieval_engine = retrieval_engine

    async def execute(self, query: str, document_id: str, top_k: int) -> list[dict[str, object]]:
        return await self.retrieval_engine.retrieve(query=query, document_id=document_id, top_k=top_k)
