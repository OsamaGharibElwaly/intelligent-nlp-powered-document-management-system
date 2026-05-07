from pydantic import BaseModel


class DocumentVersionResponse(BaseModel):
    version: int
    filename: str
    file_size: int
    storage_path: str
    index_document_id: str
    index_status: str


class DocumentMetadataResponse(BaseModel):
    document_id: str
    owner_id: str
    collection_id: str
    filename: str
    active_version: int
    is_deleted: bool
    metadata_schema_version: int
    tags: list[str]
    metadata: dict[str, str]
    versions: list[DocumentVersionResponse]


class MetadataUpdateRequest(BaseModel):
    tags: list[str] | None = None
    metadata: dict[str, str] | None = None
