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


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_role_and_quota_metadata() -> None:
    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "user"
    assert body["document_quota"] > 0
    assert body["storage_quota_bytes"] > 0


def test_invalid_credentials_rejected() -> None:
    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "user@local.dev", "password": "wrong"})
    assert response.status_code == 401


def test_viewer_cannot_upload_or_access_other_users_documents() -> None:
    client = TestClient(app)
    user_headers = _login(client, "user@local.dev", "user123")
    viewer_headers = _login(client, "viewer@local.dev", "viewer123")

    upload = client.post(
        "/upload",
        headers=user_headers,
        files={"file": ("doc.txt", b"viewer should read only", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    blocked_upload = client.post(
        "/upload",
        headers=viewer_headers,
        files={"file": ("blocked.txt", b"should fail", "text/plain")},
    )
    assert blocked_upload.status_code == 403

    retrieve = client.post(
        "/retrieve",
        headers=viewer_headers,
        json={"query": "read", "document_id": document_id, "top_k": 1},
    )
    assert retrieve.status_code == 403


def test_missing_token_rejected() -> None:
    client = TestClient(app)
    response = client.post("/query", json={"question": "q", "document_id": "doc", "top_k": 1})
    assert response.status_code == 401
