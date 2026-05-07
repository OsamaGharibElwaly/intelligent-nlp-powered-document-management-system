from fastapi import APIRouter, HTTPException

from app.dependencies import auth_service
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    try:
        result = auth_service.authenticate(payload.email, payload.password)
        return LoginResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/register", response_model=LoginResponse)
async def register(payload: RegisterRequest) -> LoginResponse:
    try:
        result = auth_service.register(payload.email, payload.password)
        return LoginResponse(**result)
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already exists" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
