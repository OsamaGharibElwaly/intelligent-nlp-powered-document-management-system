import io
import re
from dataclasses import dataclass

from docx import Document
from pypdf import PdfReader


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    order: int


class DocumentProcessingService:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 150

    def validate_extension(self, filename: str) -> None:
        lower_name = filename.lower()
        if not any(lower_name.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
            raise ValueError("Unsupported file type. Allowed: PDF, DOCX, TXT.")

    async def process(self, document_id: str, filename: str, content: bytes) -> list[DocumentChunk]:
        raw_text = self._extract_text(filename=filename, content=content)
        normalized_text = self._normalize_text(raw_text)
        return self._chunk_text(document_id=document_id, text=normalized_text)

    def _extract_text(self, filename: str, content: bytes) -> str:
        lower_name = filename.lower()
        if lower_name.endswith(".txt"):
            return content.decode("utf-8", errors="ignore")
        if lower_name.endswith(".pdf"):
            return self._extract_pdf_text(content)
        if lower_name.endswith(".docx"):
            return self._extract_docx_text(content)
        raise ValueError("Unsupported file type. Allowed: PDF, DOCX, TXT.")

    def _extract_pdf_text(self, content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)

    def _extract_docx_text(self, content: bytes) -> str:
        document = Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    def _normalize_text(self, raw_text: str) -> str:
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    def _chunk_text(self, document_id: str, text: str) -> list[DocumentChunk]:
        if not text:
            return []

        chunks: list[DocumentChunk] = []
        start = 0
        order = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.CHUNK_SIZE, text_length)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}:{order}",
                        text=chunk_text,
                        order=order,
                    )
                )
                order += 1
            if end == text_length:
                break
            start = max(0, end - self.CHUNK_OVERLAP)

        return chunks
