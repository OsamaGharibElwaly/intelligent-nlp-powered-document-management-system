from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.query import router as query_router
from app.api.routes.qa import router as qa_router
from app.api.routes.retrieve import router as retrieve_router
from app.api.routes.upload import router as upload_router
from app.config import GROQ_API_KEY

app = FastAPI(title="RAG Document Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(upload_router)
app.include_router(retrieve_router)
app.include_router(qa_router)
app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "groq_configured": str(bool(GROQ_API_KEY)).lower()}
