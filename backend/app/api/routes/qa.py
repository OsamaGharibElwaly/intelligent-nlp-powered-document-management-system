from fastapi import APIRouter, HTTPException

from app.dependencies import answer_question_use_case
from app.schemas.qa import AnswerRequest, AnswerResponse

router = APIRouter(tags=["qa"])


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(payload: AnswerRequest) -> AnswerResponse:
    try:
        answer = await answer_question_use_case.execute(
            question=payload.question,
            document_id=payload.document_id,
            top_k=payload.top_k,
        )
        return AnswerResponse(answer=answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
