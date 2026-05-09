"""Phase 2 end-to-end integration (query ↔ retrieval ↔ citations ↔ feedback)."""

import os
import re
import sys
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
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_multi_document_query_includes_both_sources_in_llm_context(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.dependencies as deps

    headers = _auth_headers(client)

    up_a = client.post(
        "/upload",
        headers=headers,
        files={"file": ("a.txt", b"ALPHA_UNIQUE_MARKER describes the alpha concept.", "text/plain")},
    )
    up_b = client.post(
        "/upload",
        headers=headers,
        files={"file": ("b.txt", b"BETA_UNIQUE_MARKER describes the beta concept.", "text/plain")},
    )
    assert up_a.status_code == 200 and up_b.status_code == 200
    doc_a = up_a.json()["document_id"]
    doc_b = up_b.json()["document_id"]

    async def fake_answer_json(system_prompt: str, user_prompt: str) -> dict[str, object]:
        assert "ALPHA_UNIQUE_MARKER" in user_prompt
        assert "BETA_UNIQUE_MARKER" in user_prompt
        m = re.search(r"\[chunk_id=([^\s]+)\s+document_id=([^\]]+)\]", user_prompt)
        assert m
        chunk_id, logical_doc = m.group(1), m.group(2)
        return {
            "paragraphs": [
                {
                    "text": "ALPHA_UNIQUE_MARKER describes the alpha concept.",
                    "citations": [{"chunk_id": chunk_id, "document_id": logical_doc}],
                }
            ]
        }

    monkeypatch.setattr(deps.llm_service, "answer_json", fake_answer_json)

    response = client.post(
        "/query",
        headers=headers,
        json={
            "question": "What do alpha and beta markers say?",
            "document_id": doc_a,
            "document_ids": [doc_a, doc_b],
            "top_k": 6,
            "retrieval_mode": "hybrid",
            "answer_mode": "flexible",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "ALPHA_UNIQUE_MARKER" in body["answer"]
    assert body["confidence"]["score"] >= 0.0
    assert isinstance(body["evidence_spans"], list)


def test_metadata_filter_can_exclude_scope_yielding_empty_answer(client: TestClient) -> None:
    headers = _auth_headers(client)
    up = client.post(
        "/upload",
        headers=headers,
        files={"file": ("tagged.txt", b"Secret content for tagged doc.", "text/plain")},
    )
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    patch = client.patch(
        f"/documents/{doc_id}/metadata",
        headers=headers,
        json={"tags": ["wanted_tag"]},
    )
    assert patch.status_code == 200

    response = client.post(
        "/query",
        headers=headers,
        json={
            "question": "What is the secret?",
            "document_id": doc_id,
            "filters": {"tags": ["other_tag"]},
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Not enough information")
    assert body["citations"] == []
    assert body["confidence"]["score"] == 0.0


def test_feedback_persisted_after_query_snapshot(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.dependencies as deps

    headers = _auth_headers(client)

    async def fake_answer_json(system_prompt: str, user_prompt: str) -> dict[str, object]:
        m = re.search(r"\[chunk_id=([^\s]+)\s+document_id=([^\]]+)\]", user_prompt)
        assert m
        chunk_id, logical_doc = m.group(1), m.group(2)
        return {
            "paragraphs": [
                {
                    "text": "Feedback probe sentence.",
                    "citations": [{"chunk_id": chunk_id, "document_id": logical_doc}],
                }
            ]
        }

    monkeypatch.setattr(deps.llm_service, "answer_json", fake_answer_json)

    up = client.post(
        "/upload",
        headers=headers,
        files={"file": ("fb.txt", b"Feedback probe sentence for persistence.", "text/plain")},
    )
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    q = client.post(
        "/query",
        headers=headers,
        json={"question": "probe", "document_id": doc_id, "top_k": 2},
    )
    assert q.status_code == 200
    answer_body = q.json()

    ret = client.post(
        "/retrieve",
        headers=headers,
        json={"query": "probe", "document_id": doc_id, "top_k": 2},
    )
    assert ret.status_code == 200
    chunks = ret.json()

    fb = client.post(
        "/feedback",
        headers=headers,
        json={
            "sentiment": "positive",
            "query": "probe",
            "document_id": doc_id,
            "answer": answer_body["answer"],
            "confidence_score": answer_body["confidence"]["score"],
            "retrieved_chunks": [{"chunk_id": c["chunk_id"], "relevance_score": c["relevance_score"]} for c in chunks],
        },
    )
    assert fb.status_code == 200
    assert fb.json().get("feedback_id")

    recent = deps.feedback_store.list_recent(limit=5)
    assert any(row.get("sentiment") == "positive" and row.get("query") == "probe" for row in recent)
