import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_processing import DocumentProcessingService


def test_validate_extension_rejects_invalid_file() -> None:
    service = DocumentProcessingService()
    with pytest.raises(ValueError):
        service.validate_extension("malicious.exe")


def test_normalize_text_cleans_spacing_and_newlines() -> None:
    service = DocumentProcessingService()
    normalized = service._normalize_text("Hello   world\r\n\r\n\r\nLine\t\tTwo")
    assert normalized == "Hello world\n\nLine Two"


def test_chunk_text_creates_ordered_chunk_ids() -> None:
    service = DocumentProcessingService()
    service.CHUNK_SIZE = 10
    service.CHUNK_OVERLAP = 2

    chunks = service._chunk_text("doc-1", "0123456789abcdef")
    assert len(chunks) >= 2
    assert chunks[0].chunk_id == "doc-1:0"
    assert chunks[1].chunk_id == "doc-1:1"
    assert chunks[0].order == 0
    assert chunks[1].order == 1


def test_process_txt_returns_chunks() -> None:
    service = DocumentProcessingService()
    content = b"RAG pipelines are deterministic and grounded."
    chunks = asyncio.run(service.process(document_id="doc-2", filename="note.txt", content=content))
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc-2:0"
    assert "RAG pipelines" in chunks[0].text
