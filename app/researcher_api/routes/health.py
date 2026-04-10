from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness(request: Request, response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {"runtime": "ok", "database": "ok", "auth": "ok"}
    try:
        request.app.state.store.fetchone("SELECT 1 AS ok", ())
    except Exception:
        checks["database"] = "error"
    if not getattr(request.app.state, "researcher_session_secret", ""):
        checks["auth"] = "error"
    if any(value != "ok" for value in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks}
    return {"status": "ready", "checks": checks}
