"""Team workspaces (Phase 4.1) — file-backed, migration-safe."""

import json
import uuid
from pathlib import Path
from threading import Lock
from typing import Any


_VALID_MEMBER_ROLES = frozenset({"owner", "editor", "viewer"})


class WorkspaceStore:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._path = self._root / "workspaces.json"
        self._lock = Lock()
        if not self._path.exists():
            self._path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, dict[str, Any]]:
        raw = self._path.read_text(encoding="utf-8").strip() or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for wid, row in parsed.items():
            if isinstance(row, dict):
                out[str(wid)] = dict(row)
        return out

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        owner = str(row.get("owner_id", "")).strip().lower()
        members_raw = row.get("members")
        members: dict[str, str] = {}
        if isinstance(members_raw, dict):
            for email, role in members_raw.items():
                e = str(email).strip().lower()
                r = str(role).strip().lower()
                if e and r in _VALID_MEMBER_ROLES and r != "owner":
                    members[e] = r
        row["workspace_id"] = str(row.get("workspace_id", "")).strip()
        row["name"] = str(row.get("name", "Workspace")).strip() or "Workspace"
        row["owner_id"] = owner
        row["members"] = members
        return row

    def create_workspace(self, *, owner_id: str, name: str) -> dict[str, Any]:
        owner = owner_id.strip().lower()
        wid = str(uuid.uuid4())
        row = self._normalize({"workspace_id": wid, "name": name, "owner_id": owner, "members": {}})
        with self._lock:
            data = self._load()
            data[wid] = row
            self._save(data)
        return dict(row)

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._load().get(workspace_id.strip())
        if row is None:
            return None
        return dict(self._normalize(dict(row)))

    def list_for_user(self, user_email: str) -> list[dict[str, Any]]:
        email = user_email.strip().lower()
        with self._lock:
            data = self._load()
        out: list[dict[str, Any]] = []
        for row in data.values():
            norm = self._normalize(dict(row))
            if norm["owner_id"] == email or email in norm["members"]:
                row_out = dict(norm)
                row_out["my_role"] = "owner" if norm["owner_id"] == email else str(norm["members"].get(email, "viewer"))
                out.append(row_out)
        return sorted(out, key=lambda r: r["name"].lower())

    def list_workspace_ids_for_user(self, user_email: str) -> set[str]:
        return {str(w["workspace_id"]) for w in self.list_for_user(user_email)}

    def member_role(self, workspace_id: str, user_email: str) -> str | None:
        ws = self.get(workspace_id)
        if ws is None:
            return None
        email = user_email.strip().lower()
        if ws["owner_id"] == email:
            return "owner"
        role = ws["members"].get(email)
        return role if role in _VALID_MEMBER_ROLES else None

    def can_edit_workspace_content(self, workspace_id: str, user_email: str) -> bool:
        role = self.member_role(workspace_id, user_email)
        return role in ("owner", "editor")

    def assert_manage_workspace(self, workspace_id: str, user_email: str) -> dict[str, Any]:
        ws = self.get(workspace_id)
        if ws is None:
            raise ValueError("Workspace not found.")
        if ws["owner_id"] != user_email.strip().lower():
            raise ValueError("Only the workspace owner can manage members.")
        return ws

    def add_or_update_member(self, workspace_id: str, *, actor_email: str, member_email: str, role: str) -> dict[str, Any]:
        r = role.strip().lower()
        if r not in _VALID_MEMBER_ROLES or r == "owner":
            raise ValueError("Invalid role (use editor or viewer).")
        self.assert_manage_workspace(workspace_id, actor_email)
        target = member_email.strip().lower()
        owner = self.get(workspace_id)["owner_id"]
        if target == owner:
            raise ValueError("Owner membership is implicit.")
        with self._lock:
            data = self._load()
            row = data.get(workspace_id)
            if row is None:
                raise ValueError("Workspace not found.")
            norm = self._normalize(dict(row))
            members = dict(norm["members"])
            members[target] = r
            norm["members"] = members
            data[workspace_id] = norm
            self._save(data)
        return dict(norm)

    def force_add_member(self, workspace_id: str, member_email: str, role: str) -> dict[str, Any]:
        """Administrator bootstrap — no owner actor required."""

        r = role.strip().lower()
        if r not in ("editor", "viewer"):
            raise ValueError("Invalid role (use editor or viewer).")
        target = member_email.strip().lower()
        with self._lock:
            data = self._load()
            row = data.get(workspace_id.strip())
            if row is None:
                raise ValueError("Workspace not found.")
            norm = self._normalize(dict(row))
            owner = norm["owner_id"]
            if target == owner:
                raise ValueError("Owner membership is implicit.")
            members = dict(norm["members"])
            members[target] = r
            norm["members"] = members
            data[workspace_id.strip()] = norm
            self._save(data)
        return dict(norm)

    def remove_member(self, workspace_id: str, *, actor_email: str, member_email: str) -> dict[str, Any]:
        self.assert_manage_workspace(workspace_id, actor_email)
        target = member_email.strip().lower()
        with self._lock:
            data = self._load()
            row = data.get(workspace_id)
            if row is None:
                raise ValueError("Workspace not found.")
            norm = self._normalize(dict(row))
            members = dict(norm["members"])
            members.pop(target, None)
            norm["members"] = members
            data[workspace_id] = norm
            self._save(data)
        return dict(norm)
