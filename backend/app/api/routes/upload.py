from fastapi import APIRouter, File, HTTPException, UploadFile

from app.dependencies import ingest_document_use_case
from app.schemas.upload import UploadResponse

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    try:
        result = await ingest_document_use_case.execute(file)
        return UploadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
