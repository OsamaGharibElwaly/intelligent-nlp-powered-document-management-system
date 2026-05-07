import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

import jwt

from app.config import JWT_SECRET, STORAGE_PATH, TOKEN_EXPIRY


@dataclass(frozen=True)
class UserRecord:
    email: str
    role: str
    document_quota: int
    storage_quota_bytes: int
    password_hash: str


class AuthService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._users_path = Path(STORAGE_PATH) / "users.json"
        self._users_path.parent.mkdir(parents=True, exist_ok=True)
        self._users = self._build_user_store()
        self._persist_users()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(f"{JWT_SECRET}:{password}".encode("utf-8")).hexdigest()

    def _build_user_store(self) -> dict[str, UserRecord]:
        # Deterministic bootstrap users for local/testing environments.
        # Passwords: admin123 / user123 / viewer123
        if not JWT_SECRET:
            return {}
        bootstrap = {
            "admin@local.dev": UserRecord(
                email="admin@local.dev",
                role="admin",
                document_quota=1000,
                storage_quota_bytes=2_000_000_000,
                password_hash=self._hash_password("admin123"),
            ),
            "user@local.dev": UserRecord(
                email="user@local.dev",
                role="user",
                document_quota=200,
                storage_quota_bytes=500_000_000,
                password_hash=self._hash_password("user123"),
            ),
            "viewer@local.dev": UserRecord(
                email="viewer@local.dev",
                role="viewer",
                document_quota=0,
                storage_quota_bytes=0,
                password_hash=self._hash_password("viewer123"),
            ),
        }
        existing = self._load_users_from_disk()
        for email, record in existing.items():
            bootstrap[email] = record
        return bootstrap

    def _load_users_from_disk(self) -> dict[str, UserRecord]:
        if not self._users_path.exists():
            return {}
        raw = self._users_path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        users: dict[str, UserRecord] = {}
        for key, value in parsed.items():
            if not isinstance(value, dict):
                continue
            email = str(value.get("email", key)).lower()
            role = str(value.get("role", "user"))
            document_quota = int(value.get("document_quota", 200))
            storage_quota_bytes = int(value.get("storage_quota_bytes", 500_000_000))
            password_hash = str(value.get("password_hash", ""))
            if not email or not password_hash:
                continue
            users[email] = UserRecord(
                email=email,
                role=role,
                document_quota=document_quota,
                storage_quota_bytes=storage_quota_bytes,
                password_hash=password_hash,
            )
        return users

    def _persist_users(self) -> None:
        serializable = {
            email: {
                "email": user.email,
                "role": user.role,
                "document_quota": user.document_quota,
                "storage_quota_bytes": user.storage_quota_bytes,
                "password_hash": user.password_hash,
            }
            for email, user in self._users.items()
        }
        self._users_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")

    def authenticate(self, email: str, password: str) -> dict[str, object]:
        if not JWT_SECRET:
            raise ValueError("JWT_SECRET is not configured.")
        user = self._users.get(email.lower())
        if user is None or user.password_hash != self._hash_password(password):
            raise ValueError("Invalid credentials.")

        token = self._create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user.role,
            "document_quota": user.document_quota,
            "storage_quota_bytes": user.storage_quota_bytes,
        }

    def register(self, email: str, password: str) -> dict[str, object]:
        if not JWT_SECRET:
            raise ValueError("JWT_SECRET is not configured.")
        normalized_email = email.lower().strip()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        with self._lock:
            if normalized_email in self._users:
                raise ValueError("User already exists.")
            user = UserRecord(
                email=normalized_email,
                role="user",
                document_quota=200,
                storage_quota_bytes=500_000_000,
                password_hash=self._hash_password(password),
            )
            self._users[normalized_email] = user
            self._persist_users()
        token = self._create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user.role,
            "document_quota": user.document_quota,
            "storage_quota_bytes": user.storage_quota_bytes,
        }

    def _create_access_token(self, user: UserRecord) -> str:
        exp = datetime.now(UTC) + timedelta(minutes=TOKEN_EXPIRY)
        payload = {
            "sub": user.email,
            "role": user.role,
            "document_quota": user.document_quota,
            "storage_quota_bytes": user.storage_quota_bytes,
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    def decode_token(self, token: str) -> dict[str, object]:
        if not JWT_SECRET:
            raise ValueError("JWT_SECRET is not configured.")
        try:
            decoded: dict[str, object] = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return decoded
        except jwt.InvalidTokenError as exc:
            raise ValueError("Invalid or expired token.") from exc
