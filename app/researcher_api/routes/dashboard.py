from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.researcher_api.auth import require_researcher_auth

router = APIRouter(prefix="/admin/api/v1/dashboard", tags=["admin-dashboard"], dependencies=[Depends(require_researcher_auth)])


@router.get("")
def get_dashboard(request: Request, focus_run_id: str | None = Query(default=None)) -> dict:
    try:
        return request.app.state.dashboard_service.get_dashboard_payload(focus_run_id=focus_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
