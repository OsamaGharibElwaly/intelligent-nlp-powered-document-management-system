from app.services.rag_pipeline import RAGPipelineService


class AnswerQuestionUseCase:
    def __init__(self, rag_pipeline_service: RAGPipelineService) -> None:
        self.rag_pipeline_service = rag_pipeline_service

    async def execute(self, question: str, document_id: str, top_k: int) -> str:
        return await self.rag_pipeline_service.run_query_flow(
            question=question,
            document_id=document_id,
            top_k=top_k,
        )
