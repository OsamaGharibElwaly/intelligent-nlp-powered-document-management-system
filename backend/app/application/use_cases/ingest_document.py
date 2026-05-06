import uuid

from fastapi import UploadFile

from app.services.document_processing import DocumentProcessingService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


class IngestDocumentUseCase:
    def __init__(
        self,
        document_processing_service: DocumentProcessingService,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self.document_processing_service = document_processing_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def execute(self, file: UploadFile) -> dict[str, str]:
        if not file.filename:
            raise ValueError("File name is required.")

        self.document_processing_service.validate_extension(file.filename)
        raw_content = await file.read()

        document_id = str(uuid.uuid4())
        chunks = await self.document_processing_service.process(
            document_id=document_id,
            filename=file.filename,
            content=raw_content,
        )
        if not chunks:
            raise ValueError("Could not extract readable text from the uploaded file.")

        embeddings = await self.embedding_service.embed_texts([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding generation failed for one or more chunks.")

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            await self.vector_store.upsert(
                document_id=document_id,
                chunk_id=chunk.chunk_id,
                order=chunk.order,
                embedding=embedding,
                text=chunk.text,
            )

        return {"document_id": document_id, "status": "processed"}
