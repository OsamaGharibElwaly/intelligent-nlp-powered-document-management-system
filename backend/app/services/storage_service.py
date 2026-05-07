from pathlib import Path


class StorageService:
    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path)
        self.documents_dir = self.root / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    def save_document(self, document_id: str, filename: str, content: bytes, version: int = 1) -> str:
        extension = Path(filename).suffix.lower()
        target = self.documents_dir / f"{document_id}__v{version}{extension}"
        target.write_bytes(content)
        return str(target)
