from fastapi import APIRouter

from app.dependencies import retrieve_chunks_use_case
from app.schemas.retrieval import RetrievalItem, RetrievalRequest

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", response_model=list[RetrievalItem])
async def retrieve_chunks(payload: RetrievalRequest) -> list[RetrievalItem]:
    results = await retrieve_chunks_use_case.execute(
        query=payload.query,
        document_id=payload.document_id,
        top_k=payload.top_k,
    )
    return [RetrievalItem(**result) for result in results]
