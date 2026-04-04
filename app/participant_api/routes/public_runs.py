from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/public/runs", tags=["public-runs"])


@router.get("/{run_slug}")
def get_public_run(run_slug: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.get_public_run_info(run_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
