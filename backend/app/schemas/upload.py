from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    status: str
