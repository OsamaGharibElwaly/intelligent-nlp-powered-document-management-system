import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.vector_store import VectorStore


def test_vector_store_upsert_and_search() -> None:
    store = VectorStore()
    asyncio.run(store.upsert("doc-a", "doc-a:0", 0, [1.0, 0.0], "alpha"))
    asyncio.run(store.upsert("doc-a", "doc-a:1", 1, [0.9, 0.1], "alpha-2"))
    results = asyncio.run(store.search([1.0, 0.0], top_k=2))
    assert len(results) == 2
    assert results[0]["chunk_id"] == "doc-a:0"
    assert results[0]["score"] >= results[1]["score"]


def test_vector_store_rejects_bad_embedding_shape() -> None:
    store = VectorStore()
    with pytest.raises(ValueError):
        asyncio.run(store.upsert("doc-b", "doc-b:0", 0, [[1.0, 0.0]], "bad-shape"))  # type: ignore[arg-type]


def test_vector_store_rejects_dimension_mismatch() -> None:
    store = VectorStore()
    asyncio.run(store.upsert("doc-c", "doc-c:0", 0, [1.0, 0.0], "first"))
    with pytest.raises(ValueError):
        asyncio.run(store.upsert("doc-c", "doc-c:1", 1, [1.0, 0.0, 0.0], "second"))
