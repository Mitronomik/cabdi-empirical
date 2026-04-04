from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.researcher_api.auth import require_researcher_auth

router = APIRouter(
    prefix="/admin/api/v1/runs", tags=["admin-diagnostics"], dependencies=[Depends(require_researcher_auth)]
)


@router.get("/{run_id}/diagnostics")
def run_diagnostics(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.diagnostics_service.get_run_diagnostics(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
