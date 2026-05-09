import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("TOKEN_EXPIRY", "60")

from app.main import app  # noqa: E402
from app.services.retrieval_storage_bias import storage_retrieval_multiplier  # noqa: E402


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_document_defaults_and_storage_filters() -> None:
    client = TestClient(app)
    headers = _auth(client)
    upload = client.post(
        "/upload",
        headers=headers,
        files={"file": ("stor.txt", b"storage layer doc content", "text/plain")},
    )
    assert upload.status_code == 200
    doc_id = upload.json()["document_id"]

    detail = client.get(f"/documents/{doc_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["read_status"] == "unread"
    assert body["reading_progress"] == 0
    assert body["priority"] == "medium"
    assert body["pinned"] is False
    assert body["archived"] is False
    assert body["ai_usage_count"] == 0
    assert body["todos"] == []

    client.patch(
        f"/documents/{doc_id}/state",
        headers=headers,
        json={"pinned": True, "priority": "high", "due_date": "2020-01-01"},
    )

    overdue = client.get("/documents", headers=headers, params={"overdue": True})
    assert overdue.status_code == 200
    assert any(d["document_id"] == doc_id for d in overdue.json())

    pinned = client.get("/documents", headers=headers, params={"pinned_only": True})
    assert pinned.status_code == 200
    assert any(d["document_id"] == doc_id for d in pinned.json())

    client.patch(f"/documents/{doc_id}/state", headers=headers, json={"archived": True})
    hidden = client.get("/documents", headers=headers)
    assert all(d["document_id"] != doc_id for d in hidden.json())
    shown = client.get("/documents", headers=headers, params={"include_archived": True})
    assert any(d["document_id"] == doc_id for d in shown.json())


def test_todos_auto_complete_document_and_activity_timeline() -> None:
    client = TestClient(app)
    headers = _auth(client)
    upload = client.post(
        "/upload",
        headers=headers,
        files={"file": ("todo.txt", b"todo workflow sample text", "text/plain")},
    )
    assert upload.status_code == 200
    doc_id = upload.json()["document_id"]

    c1 = client.post(
        f"/documents/{doc_id}/todos",
        headers=headers,
        json={"title": "First", "status": "pending"},
    )
    assert c1.status_code == 200
    c2 = client.post(f"/documents/{doc_id}/todos", headers=headers, json={"title": "Second"})
    assert c2.status_code == 200
    todos = c2.json()["todos"]
    ids = [t["todo_id"] for t in todos]
    assert len(ids) == 2

    client.patch(f"/documents/{doc_id}/todos/{ids[0]}", headers=headers, json={"status": "done"})
    mid = client.get(f"/documents/{doc_id}", headers=headers).json()
    assert mid["read_status"] != "completed"

    client.patch(f"/documents/{doc_id}/todos/{ids[1]}", headers=headers, json={"status": "done"})
    done_doc = client.get(f"/documents/{doc_id}", headers=headers).json()
    assert done_doc["read_status"] == "completed"
    assert done_doc["reading_progress"] == 100

    acts = client.get(f"/documents/{doc_id}/activity", headers=headers)
    assert acts.status_code == 200
    types = {a["activity_type"] for a in acts.json()}
    assert "marked_completed" in types

    filtered = client.get(
        f"/documents/{doc_id}/activity",
        headers=headers,
        params={"activity_type": "marked_completed"},
    )
    assert filtered.status_code == 200
    assert all(a["activity_type"] == "marked_completed" for a in filtered.json())


def test_storage_retrieval_multiplier_prefers_unread_downranks_archived() -> None:
    base = {"read_status": "unread", "archived": False, "priority": "medium"}
    archived = {**base, "archived": True}
    assert storage_retrieval_multiplier(base) > storage_retrieval_multiplier(archived)
    reading = {**base, "read_status": "reading"}
    completed = {**base, "read_status": "completed"}
    assert storage_retrieval_multiplier(base) >= storage_retrieval_multiplier(completed)
    assert storage_retrieval_multiplier(reading) >= storage_retrieval_multiplier(completed)
