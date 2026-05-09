import json
import traceback
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api.routes.admin_bootstrap import router as admin_bootstrap_router
from app.api.routes.audit import router as audit_router
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.query import router as query_router
from app.api.routes.qa import router as qa_router
from app.api.routes.retrieve import router as retrieve_router
from app.api.routes.upload import router as upload_router
from app.config import ALLOWED_ORIGINS, GROQ_API_KEY, JWT_SECRET, STORAGE_PATH
from app.dependencies import error_intelligence_store
from app.request_context import current_request_id, current_request_metrics, current_request_path

app = FastAPI(title="RAG Document Assistant")


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    from time import perf_counter

    rid = str(uuid4())
    rid_token = current_request_id.set(rid)
    path_token = current_request_path.set(request.url.path)
    metrics_payload = {"perf_start": perf_counter(), "request_id": rid, "path": request.url.path}
    metrics_token = current_request_metrics.set(metrics_payload)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        current_request_id.reset(rid_token)
        current_request_path.reset(path_token)
        current_request_metrics.reset(metrics_token)


def _http_detail_payload(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail[:8000]
    try:
        return json.dumps(detail, ensure_ascii=True)[:8000]
    except TypeError:
        return repr(detail)[:8000]


@app.exception_handler(RequestValidationError)
async def request_validation_intel_handler(request: Request, exc: RequestValidationError):
    error_intelligence_store.record(
        error_type="validation",
        severity="warning",
        endpoint=current_request_path.get() or request.url.path,
        message=f"Request validation failed: {json.dumps(exc.errors(), ensure_ascii=True)[:4000]}",
        request_id=current_request_id.get(),
        extra={"errors": exc.errors()},
    )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_intel_handler(request: Request, exc: HTTPException):
    path = current_request_path.get() or request.url.path
    rid = current_request_id.get()
    msg = _http_detail_payload(exc)
    if exc.status_code >= 500:
        error_intelligence_store.record(
            error_type="system",
            severity="critical",
            endpoint=path,
            message=msg,
            request_id=rid,
        )
    elif exc.status_code == 400:
        error_intelligence_store.record(
            error_type="validation",
            severity="warning",
            endpoint=path,
            message=msg,
            request_id=rid,
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_intel_handler(request: Request, exc: Exception):
    path = current_request_path.get() or request.url.path
    rid = current_request_id.get()
    error_intelligence_store.record(
        error_type="system",
        severity="critical",
        endpoint=path,
        message=str(exc)[:8000],
        request_id=rid,
        stack_trace=traceback.format_exc(),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(admin_bootstrap_router)
app.include_router(audit_router)
app.include_router(documents_router)
app.include_router(upload_router)
app.include_router(retrieve_router)
app.include_router(feedback_router)
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
