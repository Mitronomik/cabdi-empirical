from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-exports"])


@router.get("/{run_id}/exports")
def run_exports(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.admin_export_service.export_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
