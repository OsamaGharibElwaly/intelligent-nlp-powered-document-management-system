import json
from pathlib import Path
from threading import Lock
from typing import Any


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
            data[document_id] = {
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
