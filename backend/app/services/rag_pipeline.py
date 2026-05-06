from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_engine import RetrievalEngine


class RAGPipelineService:
    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
    ) -> None:
        self.retrieval_engine = retrieval_engine
        self.prompt_builder = prompt_builder
        self.llm_service = llm_service

    async def run_query_flow(self, question: str, document_id: str, top_k: int) -> str:
        retrieved = await self.retrieval_engine.retrieve(query=question, document_id=document_id, top_k=top_k)
        if not retrieved:
            return "Not enough information in document"

        context = [str(item["text"]) for item in retrieved]
        system_prompt, user_prompt = self.prompt_builder.build(question=question, context=context)
        answer = await self.llm_service.answer(system_prompt=system_prompt, user_prompt=user_prompt)
        return answer or "Not enough information in document"
