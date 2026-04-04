from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant_id: str
    run_slug: str
    language: Literal["en", "ru"] | None = None


@router.post("")
def create_session(req: CreateSessionRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.create_session(
            req.participant_id,
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


@router.post("/{session_id}/final-submit")
def final_submit_session(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.final_submit(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
