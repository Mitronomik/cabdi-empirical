from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    experiment_id: str
    participant_id: str
    run_id: str | None = None
    run_slug: str | None = None
    language: Literal["en", "ru"] | None = None


@router.post("")
def create_session(req: CreateSessionRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.create_session(
            req.experiment_id,
            req.participant_id,
            run_id=req.run_id,
            run_slug=req.run_slug,
            language=req.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/start")
def start_session(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
