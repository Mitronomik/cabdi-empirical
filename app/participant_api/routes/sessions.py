from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    experiment_id: str
    participant_id: str


@router.post("")
def create_session(req: CreateSessionRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.create_session(req.experiment_id, req.participant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/start")
def start_session(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
