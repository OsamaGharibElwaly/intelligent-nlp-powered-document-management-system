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

import app.config as app_config  # noqa: E402
from app.main import app  # noqa: E402


def test_admin_bootstrap_wrong_secret_forbidden(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "ADMIN_BOOTSTRAP_SECRET", "correct-secret")

    client = TestClient(app)

    login = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    promote = client.post(
        "/admin/bootstrap/promote",
        headers=headers,
        json={
            "secretCode": "wrong",
            "confirmSecretCode": "wrong",
            "targetEmail": "viewer@local.dev",
        },
    )
    assert promote.status_code == 403


def test_admin_bootstrap_promotes_user(monkeypatch) -> None:
    storage_path = Path(app_config.STORAGE_PATH)
    users_path = storage_path / "users.json"
    prev = users_path.read_text(encoding="utf-8") if users_path.exists() else None

    try:
        monkeypatch.setattr(app_config, "ADMIN_BOOTSTRAP_SECRET", "bootstrap-dev-secret")

        client = TestClient(app)

        login = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        res = client.post(
            "/admin/bootstrap/promote",
            headers=headers,
            json={
                "secretCode": "bootstrap-dev-secret",
                "confirmSecretCode": "bootstrap-dev-secret",
                "targetEmail": "viewer@local.dev",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["role"] == "admin"
        assert body["email"] == "viewer@local.dev"

        promoted_login = client.post("/auth/login", json={"email": "viewer@local.dev", "password": "viewer123"})
        assert promoted_login.status_code == 200
        assert promoted_login.json().get("role") == "admin"
    finally:
        if prev is not None:
            users_path.parent.mkdir(parents=True, exist_ok=True)
            users_path.write_text(prev, encoding="utf-8")


def test_admin_bootstrap_mismatch_confirm_forbidden(monkeypatch) -> None:
    monkeypatch.setattr(app_config, "ADMIN_BOOTSTRAP_SECRET", "sekret")

    client = TestClient(app)

    login = client.post("/auth/login", json={"email": "user@local.dev", "password": "user123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    res = client.post(
        "/admin/bootstrap/promote",
        headers=headers,
        json={
            "secretCode": "sekret",
            "confirmSecretCode": "sekret-other",
            "targetEmail": "viewer@local.dev",
        },
    )
    assert res.status_code == 403
