"""Development-only admin promotion behind a shared bootstrap secret (server-side only)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app import config as app_runtime_config
from app.auth import get_current_user
from app.dependencies import auth_service
from app.schemas.admin_bootstrap import AdminBootstrapPromoteRequest, AdminBootstrapPromoteResponse

router = APIRouter(prefix="/admin/bootstrap", tags=["admin-bootstrap"])


def _constant_time_secret_match(provided: str, expected: str) -> bool:
    if not expected:
        return False
    a = provided.encode("utf-8")
    b = expected.encode("utf-8")
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a, b)


@router.post("/promote", response_model=AdminBootstrapPromoteResponse)
async def promote_user_with_bootstrap_secret(
    payload: AdminBootstrapPromoteRequest,
    current_user: Annotated[dict[str, object], Depends(get_current_user)],
) -> AdminBootstrapPromoteResponse:
    """Authenticated callers only; promotes ``targetEmail`` to admin if bootstrap secret matches."""
    _ = current_user

    expected = (app_runtime_config.ADMIN_BOOTSTRAP_SECRET or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="Admin bootstrap is disabled (missing ADMIN_BOOTSTRAP_SECRET).")

    if payload.secretCode != payload.confirmSecretCode:
        raise HTTPException(status_code=403, detail="Secret codes do not match.")

    if not _constant_time_secret_match(payload.secretCode.strip(), expected):
        raise HTTPException(status_code=403, detail="Invalid bootstrap secret.")

    try:
        updated = auth_service.promote_to_admin_role(str(payload.targetEmail))
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AdminBootstrapPromoteResponse(
        message="User successfully promoted to admin",
        email=updated.email,
        role=updated.role,
    )
