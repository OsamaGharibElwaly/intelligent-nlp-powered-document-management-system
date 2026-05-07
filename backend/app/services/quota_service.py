class QuotaService:
    def __init__(self) -> None:
        self._usage_by_user: dict[str, dict[str, int]] = {}

    def _usage(self, email: str) -> dict[str, int]:
        return self._usage_by_user.setdefault(email, {"documents": 0, "storage_bytes": 0})

    def assert_upload_allowed(self, user: dict[str, object], file_size: int) -> None:
        email = str(user["sub"])
        usage = self._usage(email)
        document_quota = int(user.get("document_quota", 0))
        storage_quota_bytes = int(user.get("storage_quota_bytes", 0))

        if usage["documents"] + 1 > document_quota:
            raise ValueError("Document quota exceeded.")
        if usage["storage_bytes"] + file_size > storage_quota_bytes:
            raise ValueError("Storage quota exceeded.")

    def record_upload(self, user: dict[str, object], file_size: int) -> None:
        email = str(user["sub"])
        usage = self._usage(email)
        usage["documents"] += 1
        usage["storage_bytes"] += file_size
