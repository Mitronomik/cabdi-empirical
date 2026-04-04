from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.researcher_api.auth import require_researcher_auth

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-exports"], dependencies=[Depends(require_researcher_auth)])


@router.get("/{run_id}/exports")
def run_exports(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.admin_export_service.export_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
