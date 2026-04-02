from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


@router.get("/sessions/{session_id}")
def export_session(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.export_service.export_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
