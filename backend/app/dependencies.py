from app.config import STORAGE_PATH
from app.application.use_cases.answer_question import AnswerQuestionUseCase
from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.application.use_cases.retrieve_chunks import RetrieveChunksUseCase
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.document_repository import DocumentRepository
from app.services.document_processing import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.feedback_store import FeedbackStore
from app.services.learning_signals_store import LearningSignalsStore
from app.services.llm_service import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.quota_service import QuotaService
from app.services.rag_pipeline import RAGPipelineService
from app.services.retrieval_engine import RetrievalEngine
from app.services.storage_service import StorageService
from app.services.vector_store import VectorStore

vector_store = VectorStore()
document_processing_service = DocumentProcessingService()
embedding_service = EmbeddingService()
learning_signals_store = LearningSignalsStore(STORAGE_PATH)
feedback_store = FeedbackStore(STORAGE_PATH)
retrieval_engine = RetrievalEngine(
    embedding_service=embedding_service,
    vector_store=vector_store,
    learning_signals=learning_signals_store,
)
prompt_builder = PromptBuilder()
llm_service = LLMService()
auth_service = AuthService()
quota_service = QuotaService()
storage_service = StorageService(STORAGE_PATH)
document_repository = DocumentRepository(STORAGE_PATH)
audit_service = AuditService(STORAGE_PATH)
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
