from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.query import router as query_router
from app.api.routes.qa import router as qa_router
from app.api.routes.retrieve import router as retrieve_router
from app.api.routes.upload import router as upload_router
from app.config import ALLOWED_ORIGINS, GROQ_API_KEY, JWT_SECRET, STORAGE_PATH

app = FastAPI(title="RAG Document Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(documents_router)
app.include_router(upload_router)
app.include_router(retrieve_router)
app.include_router(qa_router)
app.include_router(query_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "groq_configured": str(bool(GROQ_API_KEY)).lower(),
        "jwt_configured": str(bool(JWT_SECRET)).lower(),
    }


@app.get("/ready")
async def ready() -> dict[str, str]:
    storage_configured = str(bool(STORAGE_PATH)).lower()
    return {
        "status": "ready",
        "groq_configured": str(bool(GROQ_API_KEY)).lower(),
        "jwt_configured": str(bool(JWT_SECRET)).lower(),
        "storage_configured": storage_configured,
        "origins_configured": str(bool(ALLOWED_ORIGINS)).lower(),
    }
