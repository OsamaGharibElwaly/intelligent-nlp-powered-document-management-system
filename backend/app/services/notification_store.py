"""Per-user in-app notifications (Phase 4.2)."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


_MAX_PER_USER = 250


class NotificationStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "notifications.json"
        self._lock = Lock()
        if not self._path.exists():
            self._path.write_text(json.dumps({"users": {}}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        raw = self._path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"users": {}}
        if not isinstance(parsed, dict):
            return {"users": {}}
        users = parsed.get("users")
        if not isinstance(users, dict):
            return {"users": {}}
        return {"users": dict(users)}

    def _save(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        allowed_types = frozenset({"info", "success", "warning", "error"})
        t = str(row.get("type", "info")).strip().lower()
        if t not in allowed_types:
            t = "info"
        row["type"] = t
        row["category"] = str(row.get("category", "general")).strip()[:80]
        row["title"] = str(row.get("title", "")).strip()[:500]
        row["body"] = str(row.get("body", "")).strip()[:4000]
        row["read"] = bool(row.get("read", False))
        link = row.get("link")
        row["link"] = link if isinstance(link, dict) else {}
        return row

    def append_for_user(
        self,
        *,
        user_id: str,
        type_: str,
        category: str,
        title: str,
        body: str = "",
        link: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        uid = user_id.strip().lower()
        nid = str(uuid.uuid4())
        row = self._normalize_row(
            {
                "notification_id": nid,
                "user_id": uid,
                "type": type_,
                "category": category,
                "title": title,
                "body": body,
                "read": False,
                "created_at": _iso_now(),
                "link": link or {},
            }
        )
        with self._lock:
            data = self._load()
            users: dict[str, Any] = dict(data.get("users", {}))
            bucket = users.get(uid)
            if not isinstance(bucket, list):
                bucket = []
            bucket = [dict(self._normalize_row(dict(x))) for x in bucket if isinstance(x, dict)]
            bucket.insert(0, row)
            bucket = bucket[:_MAX_PER_USER]
            users[uid] = bucket
            data["users"] = users
            self._save(data)
        return dict(row)

    def append_for_users(
        self,
        recipients: list[str],
        *,
        type_: str,
        category: str,
        title: str,
        body: str = "",
        link: dict[str, Any] | None = None,
    ) -> None:
        seen: set[str] = set()
        for r in recipients:
            e = str(r).strip().lower()
            if not e or e in seen:
                continue
            seen.add(e)
            self.append_for_user(user_id=e, type_=type_, category=category, title=title, body=body, link=link)

    def list_for_user(self, user_id: str, *, limit: int = 100, unread_only: bool = False) -> list[dict[str, Any]]:
        uid = user_id.strip().lower()
        with self._lock:
            data = self._load()
            bucket = data.get("users", {}).get(uid)
            if not isinstance(bucket, list):
                return []
            rows = [dict(self._normalize_row(dict(x))) for x in bucket if isinstance(x, dict)]
        if unread_only:
            rows = [r for r in rows if not r.get("read")]
        return rows[: max(1, min(limit, 500))]

    def unread_count(self, user_id: str) -> int:
        return len(self.list_for_user(user_id, limit=500, unread_only=True))

    def mark_read(self, user_id: str, notification_id: str) -> dict[str, Any] | None:
        uid = user_id.strip().lower()
        nid = notification_id.strip()
        with self._lock:
            data = self._load()
            users: dict[str, Any] = dict(data.get("users", {}))
            bucket = users.get(uid)
            if not isinstance(bucket, list):
                return None
            updated_bucket: list[dict[str, Any]] = []
            found: dict[str, Any] | None = None
            for item in bucket:
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                if str(row.get("notification_id", "")) == nid:
                    row["read"] = True
                    found = self._normalize_row(row)
                    updated_bucket.append(found)
                else:
                    updated_bucket.append(self._normalize_row(row))
            if found is None:
                return None
            users[uid] = updated_bucket
            data["users"] = users
            self._save(data)
        return dict(found)

    def mark_all_read(self, user_id: str) -> int:
        uid = user_id.strip().lower()
        changed = 0
        with self._lock:
            data = self._load()
            users: dict[str, Any] = dict(data.get("users", {}))
            bucket = users.get(uid)
            if not isinstance(bucket, list):
                return 0
            new_bucket: list[dict[str, Any]] = []
            for item in bucket:
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                if not row.get("read"):
                    row["read"] = True
                    changed += 1
                new_bucket.append(self._normalize_row(row))
            users[uid] = new_bucket
            data["users"] = users
            self._save(data)
        return changed
