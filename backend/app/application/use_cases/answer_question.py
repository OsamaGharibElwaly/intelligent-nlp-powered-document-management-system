from typing import Any

from app.services.rag_pipeline import RAGPipelineService


class AnswerQuestionUseCase:
    def __init__(self, rag_pipeline_service: RAGPipelineService) -> None:
        self.rag_pipeline_service = rag_pipeline_service

    async def execute(
        self,
        question: str,
        document_id: str | None,
        top_k: int,
        *,
        metadata_by_index_document_id: dict[str, dict[str, object]] | None = None,
        retrieval_mode: str = "hybrid",
        answer_mode: str = "flexible",
        answer_length: str = "medium",
    ) -> dict[str, Any]:
        return await self.rag_pipeline_service.run_query_flow(
            question=question,
            document_id=document_id,
            top_k=top_k,
            metadata_by_index_document_id=metadata_by_index_document_id,
            retrieval_mode=retrieval_mode,
            answer_mode=answer_mode,
            answer_length=answer_length,
        )
