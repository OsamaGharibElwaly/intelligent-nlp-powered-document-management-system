from app.application.use_cases.answer_question import AnswerQuestionUseCase
from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.application.use_cases.retrieve_chunks import RetrieveChunksUseCase
from app.services.document_processing import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.rag_pipeline import RAGPipelineService
from app.services.retrieval_engine import RetrievalEngine
from app.services.vector_store import VectorStore

vector_store = VectorStore()
document_processing_service = DocumentProcessingService()
embedding_service = EmbeddingService()
retrieval_engine = RetrievalEngine(embedding_service=embedding_service, vector_store=vector_store)
prompt_builder = PromptBuilder()
llm_service = LLMService()
rag_pipeline_service = RAGPipelineService(
    retrieval_engine=retrieval_engine,
    prompt_builder=prompt_builder,
    llm_service=llm_service,
)

ingest_document_use_case = IngestDocumentUseCase(
    document_processing_service=document_processing_service,
    embedding_service=embedding_service,
    vector_store=vector_store,
)
retrieve_chunks_use_case = RetrieveChunksUseCase(retrieval_engine=retrieval_engine)
answer_question_use_case = AnswerQuestionUseCase(
    rag_pipeline_service=rag_pipeline_service,
)
