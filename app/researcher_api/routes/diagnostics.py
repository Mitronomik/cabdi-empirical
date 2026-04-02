from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-diagnostics"])


@router.get("/{run_id}/diagnostics")
def run_diagnostics(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.diagnostics_service.get_run_diagnostics(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
