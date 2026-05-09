import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


_READ_STATUSES = frozenset({"unread", "reading", "completed"})
_PRIORITIES = frozenset({"low", "medium", "high"})
_TODO_STATUSES = frozenset({"pending", "done"})


class DocumentRepository:
    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self._root / "metadata.json"
        self._lock = Lock()
        if not self._metadata_path.exists():
            self._metadata_path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, dict[str, Any]]:
        data = self._metadata_path.read_text(encoding="utf-8").strip() or "{}"
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            return {}
        normalized: dict[str, dict[str, Any]] = {}
        for doc_id, value in parsed.items():
            if not isinstance(value, dict):
                continue
            if "versions" in value and "active_version" in value and "is_deleted" in value:
                normalized_value = dict(value)
                normalized_value["metadata_schema_version"] = int(normalized_value.get("metadata_schema_version", 1))
                normalized_value["tags"] = self._normalize_tags(normalized_value.get("tags"))
                normalized_value["metadata"] = self._normalize_metadata(normalized_value.get("metadata"))
                self._normalize_lifecycle(normalized_value)
                normalized[doc_id] = normalized_value
                continue
            # Backward compatibility for pre-versioning metadata.
            filename = str(value.get("filename", "document"))
            file_size = int(value.get("file_size", 0))
            storage_path = str(value.get("storage_path", ""))
            normalized[doc_id] = {
                "document_id": str(value.get("document_id", doc_id)),
                "owner_id": str(value.get("owner_id", "")),
                "collection_id": str(value.get("collection_id", "default")),
                "filename": filename,
                "active_version": 1,
                "is_deleted": False,
                "metadata_schema_version": 1,
                "tags": [],
                "metadata": {},
                "versions": [
                    {
                        "version": 1,
                        "filename": filename,
                        "file_size": file_size,
                        "storage_path": storage_path,
                        "index_document_id": str(value.get("document_id", doc_id)),
                        "index_status": "processed",
                    }
                ],
            }
            self._normalize_lifecycle(normalized[doc_id])
        return normalized

    def _normalize_tags(self, tags: Any) -> list[str]:
        if not isinstance(tags, list):
            return []
        cleaned = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
        return sorted(set(cleaned))

    def _normalize_metadata(self, metadata: Any) -> dict[str, str]:
        if not isinstance(metadata, dict):
            return {}
        normalized = {str(k).strip(): str(v).strip() for k, v in metadata.items() if str(k).strip()}
        return dict(sorted(normalized.items(), key=lambda item: item[0]))

    def _normalize_todos(self, raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("todo_id", "") or "").strip() or str(uuid.uuid4())
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            st = str(item.get("status", "pending")).strip().lower()
            if st not in _TODO_STATUSES:
                st = "pending"
            desc = item.get("description")
            description = None if desc is None else str(desc).strip() or None
            due = item.get("due_date")
            due_date = None if due is None or str(due).strip() == "" else str(due).strip()[:10]
            cat = item.get("completed_at")
            completed_at = None if cat is None or str(cat).strip() == "" else str(cat).strip()
            out.append(
                {
                    "todo_id": tid,
                    "title": title[:500],
                    "description": description,
                    "status": st,
                    "due_date": due_date,
                    "completed_at": completed_at,
                }
            )
        return out

    def _normalize_lifecycle(self, doc: dict[str, Any]) -> dict[str, Any]:
        rs = str(doc.get("read_status", "unread")).strip().lower()
        if rs not in _READ_STATUSES:
            rs = "unread"
        pr = str(doc.get("priority", "medium")).strip().lower()
        if pr not in _PRIORITIES:
            pr = "medium"
        prog = int(doc.get("reading_progress", 0) or 0)
        prog = max(0, min(100, prog))
        cd = doc.get("completion_date")
        completion_date = None if cd is None or str(cd).strip() == "" else str(cd).strip()[:10]
        lr = doc.get("last_read_at")
        last_read_at = None if lr is None or str(lr).strip() == "" else str(lr).strip()
        dd = doc.get("due_date")
        due_date = None if dd is None or str(dd).strip() == "" else str(dd).strip()[:10]
        doc["read_status"] = rs
        doc["completion_date"] = completion_date
        doc["last_read_at"] = last_read_at
        doc["reading_progress"] = prog
        doc["priority"] = pr
        doc["due_date"] = due_date
        doc["pinned"] = bool(doc.get("pinned", False))
        doc["archived"] = bool(doc.get("archived", False))
        doc["ai_usage_count"] = int(doc.get("ai_usage_count", 0) or 0)
        doc["todos"] = self._normalize_todos(doc.get("todos"))
        doc["storage_schema_version"] = int(doc.get("storage_schema_version", 1))
        return doc

    def _sync_completion_from_todos(self, doc: dict[str, Any]) -> dict[str, Any]:
        todos: list[dict[str, Any]] = list(doc.get("todos", []))
        if not todos:
            return doc
        all_done = all(str(t.get("status", "")).lower() == "done" for t in todos)
        if not all_done:
            return doc
        today = datetime.now(UTC).date().isoformat()
        doc["read_status"] = "completed"
        doc["reading_progress"] = 100
        doc["completion_date"] = doc.get("completion_date") or today
        return doc

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self._metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(
        self,
        document_id: str,
        owner_id: str,
        collection_id: str,
        filename: str,
        file_size: int,
        storage_path: str,
        index_document_id: str,
    ) -> None:
        with self._lock:
            data = self._load()
            row = {
                "document_id": document_id,
                "owner_id": owner_id,
                "collection_id": collection_id,
                "filename": filename,
                "active_version": 1,
                "is_deleted": False,
                "metadata_schema_version": 1,
                "tags": [],
                "metadata": {},
                "versions": [
                    {
                        "version": 1,
                        "filename": filename,
                        "file_size": file_size,
                        "storage_path": storage_path,
                        "index_document_id": index_document_id,
                        "index_status": "processed",
                    }
                ],
            }
            self._normalize_lifecycle(row)
            data[document_id] = row
            self._save(data)

    def get(self, document_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._load().get(document_id)

    def list_for_user(self, user: dict[str, object]) -> list[dict[str, Any]]:
        role = str(user.get("role", ""))
        owner = str(user.get("sub", ""))
        with self._lock:
            data = self._load()
        docs = list(data.values()) if role == "admin" else [doc for doc in data.values() if str(doc.get("owner_id", "")) == owner]
        return [doc for doc in docs if not bool(doc.get("is_deleted", False))]

    def assert_access(self, user: dict[str, object], document_id: str) -> dict[str, Any]:
        doc = self.get(document_id)
        if doc is None:
            raise ValueError("Document not found.")
        role = str(user.get("role", ""))
        requester = str(user.get("sub", ""))
        if role != "admin" and str(doc.get("owner_id", "")) != requester:
            raise ValueError("Access denied for this document.")
        if bool(doc.get("is_deleted", False)):
            raise ValueError("Document is deleted.")
        return doc

    def assert_owner_or_admin(self, user: dict[str, object], document_id: str) -> dict[str, Any]:
        doc = self.get(document_id)
        if doc is None:
            raise ValueError("Document not found.")
        role = str(user.get("role", ""))
        requester = str(user.get("sub", ""))
        if role != "admin" and str(doc.get("owner_id", "")) != requester:
            raise ValueError("Access denied for this document.")
        return doc

    def append_version(
        self,
        document_id: str,
        filename: str,
        file_size: int,
        storage_path: str,
        index_document_id: str,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            versions = list(doc.get("versions", []))
            next_version = len(versions) + 1
            versions.append(
                {
                    "version": next_version,
                    "filename": filename,
                    "file_size": file_size,
                    "storage_path": storage_path,
                    "index_document_id": index_document_id,
                    "index_status": "processed",
                }
            )
            doc["filename"] = filename
            doc["active_version"] = next_version
            doc["is_deleted"] = False
            doc["versions"] = versions
            data[document_id] = doc
            self._save(data)
            return doc

    def update_metadata(
        self,
        document_id: str,
        tags: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            if tags is not None:
                doc["tags"] = self._normalize_tags(tags)
            if metadata is not None:
                doc["metadata"] = self._normalize_metadata(metadata)
            doc["metadata_schema_version"] = int(doc.get("metadata_schema_version", 1))
            data[document_id] = doc
            self._save(data)
            return doc

    def get_active_version(self, document_id: str) -> dict[str, Any]:
        with self._lock:
            doc = self._load().get(document_id)
        if doc is None:
            raise ValueError("Document not found.")
        if bool(doc.get("is_deleted", False)):
            raise ValueError("Document is deleted.")
        active_version = int(doc.get("active_version", 1))
        versions = list(doc.get("versions", []))
        for version in versions:
            if int(version.get("version", 0)) == active_version:
                return version
        raise ValueError("Active version not found.")

    def soft_delete(self, document_id: str) -> None:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc["is_deleted"] = True
            data[document_id] = doc
            self._save(data)

    def restore(self, document_id: str, version: int | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            versions = list(doc.get("versions", []))
            if version is not None:
                if not any(int(item.get("version", 0)) == version for item in versions):
                    raise ValueError("Version not found.")
                doc["active_version"] = version
            doc["is_deleted"] = False
            data[document_id] = doc
            self._save(data)
            return doc

    def update_lifecycle_state(
        self,
        document_id: str,
        *,
        read_status: str | None = None,
        completion_date: str | None = None,
        last_read_at: str | None = None,
        reading_progress: int | None = None,
        priority: str | None = None,
        due_date: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        """Deterministic merge of lifecycle fields (storage layer)."""
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc = dict(doc)
            self._normalize_lifecycle(doc)

            if read_status is not None:
                rs = read_status.strip().lower()
                if rs not in _READ_STATUSES:
                    raise ValueError("Invalid read_status.")
                doc["read_status"] = rs
                if rs == "completed":
                    doc["reading_progress"] = 100
                    today = datetime.now(UTC).date().isoformat()
                    doc["completion_date"] = str(doc.get("completion_date") or today)[:10]
                elif rs == "unread":
                    doc["completion_date"] = None

            if completion_date is not None:
                doc["completion_date"] = None if str(completion_date).strip() == "" else str(completion_date).strip()[:10]

            if last_read_at is not None:
                doc["last_read_at"] = None if str(last_read_at).strip() == "" else str(last_read_at).strip()

            if reading_progress is not None:
                rp = max(0, min(100, int(reading_progress)))
                doc["reading_progress"] = rp
                if rp >= 100:
                    doc["read_status"] = "completed"
                    today_iso = datetime.now(UTC).date().isoformat()
                    doc["completion_date"] = str(doc.get("completion_date") or today_iso)[:10]

            if priority is not None:
                pr = priority.strip().lower()
                if pr not in _PRIORITIES:
                    raise ValueError("Invalid priority.")
                doc["priority"] = pr

            if due_date is not None:
                doc["due_date"] = None if str(due_date).strip() == "" else str(due_date).strip()[:10]

            if pinned is not None:
                doc["pinned"] = bool(pinned)

            if archived is not None:
                doc["archived"] = bool(archived)

            self._normalize_lifecycle(doc)
            data[document_id] = doc
            self._save(data)
            return doc

    def record_read_progress(self, document_id: str, reading_progress: int) -> dict[str, Any]:
        prog = max(0, min(100, int(reading_progress)))
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc = dict(doc)
            self._normalize_lifecycle(doc)
            doc["reading_progress"] = prog
            doc["last_read_at"] = now_iso
            if prog >= 100:
                doc["read_status"] = "completed"
                today = datetime.now(UTC).date().isoformat()
                doc["completion_date"] = str(doc.get("completion_date") or today)[:10]
            elif prog > 0:
                doc["read_status"] = "reading"
            self._normalize_lifecycle(doc)
            data[document_id] = doc
            self._save(data)
            return doc

    def create_todo(
        self,
        document_id: str,
        *,
        title: str,
        description: str | None = None,
        due_date: str | None = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        st = str(status).strip().lower()
        if st not in _TODO_STATUSES:
            raise ValueError("Invalid todo status.")
        todo_id = str(uuid.uuid4())
        completed_at = None
        if st == "done":
            completed_at = datetime.now(UTC).isoformat()
        row = {
            "todo_id": todo_id,
            "title": str(title).strip()[:500],
            "description": None if description is None else str(description).strip() or None,
            "status": st,
            "due_date": None if due_date is None or str(due_date).strip() == "" else str(due_date).strip()[:10],
            "completed_at": completed_at,
        }
        if not row["title"]:
            raise ValueError("Todo title is required.")
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc = dict(doc)
            self._normalize_lifecycle(doc)
            todos = list(doc.get("todos", []))
            todos.append(row)
            doc["todos"] = self._normalize_todos(todos)
            doc = self._sync_completion_from_todos(doc)
            self._normalize_lifecycle(doc)
            data[document_id] = doc
            self._save(data)
            return doc

    def update_todo(
        self,
        document_id: str,
        todo_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc = dict(doc)
            self._normalize_lifecycle(doc)
            todos = list(doc.get("todos", []))
            found = False
            updated: list[dict[str, Any]] = []
            for item in todos:
                if str(item.get("todo_id", "")) != todo_id:
                    updated.append(dict(item))
                    continue
                found = True
                row = dict(item)
                if title is not None:
                    row["title"] = str(title).strip()[:500]
                if description is not None:
                    row["description"] = None if str(description).strip() == "" else str(description).strip()
                if due_date is not None:
                    row["due_date"] = None if str(due_date).strip() == "" else str(due_date).strip()[:10]
                if status is not None:
                    st = str(status).strip().lower()
                    if st not in _TODO_STATUSES:
                        raise ValueError("Invalid todo status.")
                    row["status"] = st
                    if st == "done":
                        row["completed_at"] = row.get("completed_at") or datetime.now(UTC).isoformat()
                    else:
                        row["completed_at"] = None
                if not str(row.get("title", "")).strip():
                    raise ValueError("Todo title is required.")
                updated.append(row)
            if not found:
                raise ValueError("Todo not found.")
            doc["todos"] = self._normalize_todos(updated)
            doc = self._sync_completion_from_todos(doc)
            self._normalize_lifecycle(doc)
            data[document_id] = doc
            self._save(data)
            return doc

    def delete_todo(self, document_id: str, todo_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            doc = data.get(document_id)
            if doc is None:
                raise ValueError("Document not found.")
            doc = dict(doc)
            self._normalize_lifecycle(doc)
            todos = [dict(t) for t in doc.get("todos", []) if str(t.get("todo_id", "")) != todo_id]
            if len(todos) == len(doc.get("todos", [])):
                raise ValueError("Todo not found.")
            doc["todos"] = self._normalize_todos(todos)
            doc = self._sync_completion_from_todos(doc)
            self._normalize_lifecycle(doc)
            data[document_id] = doc
            self._save(data)
            return doc

    def bulk_increment_ai_usage(self, logical_document_ids: set[str]) -> None:
        if not logical_document_ids:
            return
        with self._lock:
            data = self._load()
            changed = False
            for lid in logical_document_ids:
                doc = data.get(lid)
                if doc is None:
                    continue
                doc = dict(doc)
                self._normalize_lifecycle(doc)
                doc["ai_usage_count"] = int(doc.get("ai_usage_count", 0) or 0) + 1
                data[lid] = doc
                changed = True
            if changed:
                self._save(data)
