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


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_metadata_updates_are_deterministic_and_filterable() -> None:
    client = TestClient(app)
    headers = _auth(client)

    upload = client.post(
        "/upload",
        headers=headers,
        data={"collection_id": "ops"},
        files={"file": ("taggable.txt", b"metadata tagging content", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    patch = client.patch(
        f"/documents/{document_id}/metadata",
        headers=headers,
        json={"tags": ["Finance", "urgent", "finance"], "metadata": {"department": "legal", "priority": "high"}},
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["metadata_schema_version"] == 1
    assert body["tags"] == ["finance", "urgent"]
    assert body["metadata"] == {"department": "legal", "priority": "high"}

    patch_again = client.patch(
        f"/documents/{document_id}/metadata",
        headers=headers,
        json={"tags": ["urgent", "finance", "finance"], "metadata": {"priority": "high", "department": "legal"}},
    )
    assert patch_again.status_code == 200
    assert patch_again.json()["tags"] == ["finance", "urgent"]
    assert patch_again.json()["metadata"] == {"department": "legal", "priority": "high"}

    filtered_by_tag = client.get("/documents", headers=headers, params={"tag": "finance"})
    assert filtered_by_tag.status_code == 200
    assert any(item["document_id"] == document_id for item in filtered_by_tag.json())

    filtered_by_metadata = client.get(
        "/documents",
        headers=headers,
        params={"metadata_key": "department", "metadata_value": "legal"},
    )
    assert filtered_by_metadata.status_code == 200
    assert any(item["document_id"] == document_id for item in filtered_by_metadata.json())
