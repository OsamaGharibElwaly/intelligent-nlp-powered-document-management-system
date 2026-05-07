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


def _auth(client: TestClient, email: str = "user@local.dev", password: str = "user123") -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_document_versioning_soft_delete_and_restore() -> None:
    client = TestClient(app)
    headers = _auth(client)

    upload = client.post(
        "/upload",
        headers=headers,
        data={"collection_id": "contracts"},
        files={"file": ("agreement.txt", b"original contract terms", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    v2 = client.post(
        f"/documents/{document_id}/versions",
        headers=headers,
        files={"file": ("agreement.txt", b"updated contract terms", "text/plain")},
    )
    assert v2.status_code == 200
    assert v2.json()["active_version"] == 2

    versions = client.get(f"/documents/{document_id}/versions", headers=headers)
    assert versions.status_code == 200
    payload = versions.json()
    assert len(payload) == 2
    assert payload[0]["version"] == 1
    assert payload[1]["version"] == 2

    deleted = client.post(f"/documents/{document_id}/delete", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["is_deleted"] is True

    hidden_from_list = client.get("/documents", headers=headers)
    assert hidden_from_list.status_code == 200
    assert all(item["document_id"] != document_id for item in hidden_from_list.json())

    blocked_query = client.post(
        "/query",
        headers=headers,
        json={"question": "what changed?", "document_id": document_id, "top_k": 1},
    )
    assert blocked_query.status_code in (403, 404)

    restored = client.post(f"/documents/{document_id}/restore", headers=headers, data={"version": "1"})
    assert restored.status_code == 200
    assert restored.json()["is_deleted"] is False
    assert restored.json()["active_version"] == 1
