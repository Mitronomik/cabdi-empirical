from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_slug: str
    language: Literal["en", "ru"] | None = None
    resume_token: str | None = None


class ResumeInfoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_slug: str
    resume_token: str


@router.post("")
def create_session(req: CreateSessionRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.create_session(
            run_slug=req.run_slug,
            language=req.language,
            resume_token=req.resume_token,
        )
    except ValueError as exc:
        message = str(exc)
        if message == "resume_not_allowed:session_finalized":
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.post("/resume-info")
def resume_info(req: ResumeInfoRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.get_resume_info(run_slug=req.run_slug, resume_token=req.resume_token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resume")
def resume_session(req: ResumeInfoRequest, request: Request) -> dict:
    try:
        return request.app.state.session_service.resume_session(run_slug=req.run_slug, resume_token=req.resume_token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/start")
def start_session(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{session_id}/progress")
def session_progress(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.get_progress_info(session_id)
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
