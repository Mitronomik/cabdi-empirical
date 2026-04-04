from __future__ import annotations

from fastapi.responses import FileResponse
from fastapi import APIRouter, Depends, HTTPException, Request

from app.researcher_api.auth import require_researcher_auth

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-exports"], dependencies=[Depends(require_researcher_auth)])


@router.get("/{run_id}/exports")
def run_exports(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.admin_export_service.export_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/exports/artifacts/{artifact_type}")
def download_run_export_artifact(run_id: str, artifact_type: str, request: Request) -> FileResponse:
    try:
        path, media_type = request.app.state.admin_export_service.get_artifact_path(run_id, artifact_type)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path=path, media_type=media_type, filename=path.name)
