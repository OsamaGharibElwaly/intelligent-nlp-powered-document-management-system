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


def test_audit_logs_and_usage_history_are_recorded() -> None:
    client = TestClient(app)
    user_headers = _login(client, "user@local.dev", "user123")
    admin_headers = _login(client, "admin@local.dev", "admin123")

    upload = client.post(
        "/upload",
        headers=user_headers,
        data={"collection_id": "audit"},
        files={"file": ("audit.txt", b"audit logging baseline", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    query = client.post(
        "/query",
        headers=user_headers,
        json={"question": "what is this about?", "document_id": document_id, "top_k": 1},
    )
    assert query.status_code == 200

    document_access = client.get(f"/documents/{document_id}", headers=user_headers)
    assert document_access.status_code == 200

    usage = client.get("/audit/usage-history", headers=user_headers)
    assert usage.status_code == 200
    usage_payload = usage.json()
    assert usage_payload["user_id"] == "user@local.dev"
    assert len(usage_payload["query_history"]) >= 1
    assert document_id in usage_payload["last_accessed_documents"]

    admin_logs = client.get("/audit/logs", headers=admin_headers, params={"actor": "user@local.dev"})
    assert admin_logs.status_code == 200
    actions = [entry["action"] for entry in admin_logs.json()]
    assert "document_upload" in actions
    assert "query" in actions
    assert "document_access" in actions


def test_audit_observability_metrics_requires_admin_and_summarizes() -> None:
    client = TestClient(app)
    user_headers = _login(client, "user@local.dev", "user123")
    admin_headers = _login(client, "admin@local.dev", "admin123")

    denied = client.get("/audit/metrics/summary", headers=user_headers, params={"range": "24h"})
    assert denied.status_code == 403

    ok = client.get("/audit/metrics/summary", headers=admin_headers, params={"range": "24h"})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["range"] == "24h"
    assert "buckets" in payload and "totals" in payload
    assert "alert_thresholds" in payload

    csv_export = client.get("/audit/metrics/export", headers=admin_headers, params={"range": "24h", "format": "csv"})
    assert csv_export.status_code == 200
    assert "timestamp" in csv_export.text


def test_audit_error_events_requires_admin_and_returns_list() -> None:
    client = TestClient(app)
    user_headers = _login(client, "user@local.dev", "user123")
    admin_headers = _login(client, "admin@local.dev", "admin123")

    denied = client.get("/audit/error-events", headers=user_headers)
    assert denied.status_code == 403

    ok = client.get("/audit/error-events", headers=admin_headers, params={"limit": 10})
    assert ok.status_code == 200
    rows = ok.json()
    assert isinstance(rows, list)
