import os
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("TOKEN_EXPIRY", "60")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _auth_headers(client: TestClient, email: str = "user@local.dev", password: str = "user123") -> dict[str, str]:
    login_response = client.post("/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_valid_file_processed_successfully(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/upload",
        headers=headers,
        files={"file": ("notes.txt", b"RAG systems retrieve evidence before generating answers.", "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert isinstance(body["document_id"], str) and body["document_id"]


def test_upload_invalid_file_rejected(client: TestClient) -> None:
    headers = _auth_headers(client)
    response = client.post(
        "/upload",
        headers=headers,
        files={"file": ("image.png", b"fake", "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_retrieval_known_query_returns_relevant_chunk(client: TestClient) -> None:
    headers = _auth_headers(client)
    upload_response = client.post(
        "/upload",
        headers=headers,
        files={
            "file": (
                "knowledge.txt",
                b"Groq is used for generation.\nFAISS stores vectors.\nThe sky is blue.",
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    retrieve_response = client.post(
        "/retrieve",
        headers=headers,
        json={"query": "where are vectors stored", "document_id": document_id, "top_k": 3},
    )
    assert retrieve_response.status_code == 200
    results = retrieve_response.json()
    assert len(results) > 0
    assert any("FAISS stores vectors" in item["chunk_text"] for item in results)


def test_llm_grounding_uses_retrieved_context_only(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.dependencies as deps
    headers = _auth_headers(client)

    async def fake_answer_json(system_prompt: str, user_prompt: str) -> dict[str, object]:
        assert "grounded qa system" in system_prompt.lower()
        assert "CONTEXT:" in user_prompt
        match = re.search(r"\[chunk_id=([^\s]+)\s+document_id=([^\]]+)\]", user_prompt)
        assert match
        chunk_id, document_id = match.group(1), match.group(2)
        return {
            "paragraphs": [
                {
                    "text": "FAISS stores vectors.",
                    "citations": [{"chunk_id": chunk_id, "document_id": document_id}],
                }
            ]
        }

    monkeypatch.setattr(deps.llm_service, "answer_json", fake_answer_json)

    upload_response = client.post(
        "/upload",
        headers=headers,
        files={"file": ("context.txt", b"FAISS stores vectors.", "text/plain")},
    )
    document_id = upload_response.json()["document_id"]

    answer_response = client.post(
        "/query",
        headers=headers,
        json={"question": "Where are vectors stored?", "document_id": document_id, "top_k": 1},
    )
    assert answer_response.status_code == 200
    body = answer_response.json()
    assert body["answer"] == "FAISS stores vectors."
    assert len(body["citations"]) >= 1
    assert "confidence" in body and "score" in body["confidence"]
    assert "evidence_spans" in body and isinstance(body["evidence_spans"], list)


def test_determinism_and_metrics(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.dependencies as deps
    headers = _auth_headers(client)

    async def deterministic_answer_json(system_prompt: str, user_prompt: str) -> dict[str, object]:
        match = re.search(
            r"\[chunk_id=([^\s]+)\s+document_id=([^\]]+)\]\s*\n(.+?)(?=\n\n\[chunk_id=|\n\nQUESTION:)",
            user_prompt,
            re.DOTALL,
        )
        assert match
        chunk_id, document_id, chunk_body = match.group(1), match.group(2), match.group(3).strip()
        return {
            "paragraphs": [
                {
                    "text": chunk_body,
                    "citations": [{"chunk_id": chunk_id, "document_id": document_id}],
                }
            ]
        }

    monkeypatch.setattr(deps.llm_service, "answer_json", deterministic_answer_json)

    upload_response = client.post(
        "/upload",
        headers=headers,
        files={
            "file": (
                "deterministic.txt",
                b"Deterministic systems produce same output for same input.",
                "text/plain",
            )
        },
    )
    document_id = upload_response.json()["document_id"]

    payload = {"question": "What do deterministic systems do?", "document_id": document_id, "top_k": 1}

    start = time.perf_counter()
    answer_one = client.post("/query", json=payload, headers=headers)
    elapsed_ms = (time.perf_counter() - start) * 1000
    answer_two = client.post("/query", json=payload, headers=headers)

    assert answer_one.status_code == 200
    assert answer_two.status_code == 200
    assert answer_one.json() == answer_two.json()

    retrieval_response = client.post(
        "/retrieve",
        headers=headers,
        json={"query": payload["question"], "document_id": document_id, "top_k": 1},
    )
    retrieval_items = retrieval_response.json()
    assert len(retrieval_items) == 1

    retrieval_accuracy = 1.0 if "Deterministic systems produce same output" in retrieval_items[0]["chunk_text"] else 0.0
    context_relevance_score = retrieval_items[0]["relevance_score"]

    assert retrieval_accuracy >= 1.0
    assert elapsed_ms >= 0.0
    assert context_relevance_score >= 0.0
