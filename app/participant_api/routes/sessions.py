from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from typing import Literal

from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["sessions"])

LEGACY_ALIAS_DEPRECATION_NOTE = (
    "Legacy /api/v1/sessions routes are transitional aliases. "
    "Use canonical /api/v1/public/... participant routes."
)
LEGACY_ALIAS_SUNSET = "2026-12-31"


def _mark_legacy_alias(response: Response) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = LEGACY_ALIAS_SUNSET
    response.headers["X-API-Warn"] = LEGACY_ALIAS_DEPRECATION_NOTE


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_slug: str | None = None
    language: Literal["en", "ru"] | None = None
    resume_token: str | None = None


class ResumeInfoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_slug: str | None = None
    resume_token: str


def _create_session_impl(req: CreateSessionRequest, request: Request, run_slug: str | None = None) -> dict:
    target_run_slug = run_slug or req.run_slug
    if target_run_slug is None:
        raise HTTPException(status_code=400, detail="run_slug_required")
    if req.run_slug is not None and run_slug is not None and req.run_slug != run_slug:
        raise HTTPException(status_code=400, detail="run_slug_mismatch")
    try:
        return request.app.state.session_service.create_session(
            run_slug=target_run_slug,
            language=req.language,
            resume_token=req.resume_token,
        )
    except ValueError as exc:
        message = str(exc)
        if message == "resume_not_allowed:session_finalized":
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc


@router.post("/api/v1/public/runs/{run_slug}/sessions")
def create_session(req: CreateSessionRequest, request: Request, run_slug: str) -> dict:
    return _create_session_impl(req, request, run_slug)


@router.post(
    "/api/v1/sessions",
    deprecated=True,
    summary="(Deprecated) Create participant session via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def create_session_legacy(req: CreateSessionRequest, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _create_session_impl(req, request)


def _resume_info_impl(req: ResumeInfoRequest, request: Request, run_slug: str | None = None) -> dict:
    target_run_slug = run_slug or req.run_slug
    if target_run_slug is None:
        raise HTTPException(status_code=400, detail="run_slug_required")
    try:
        return request.app.state.session_service.get_resume_info(run_slug=target_run_slug, resume_token=req.resume_token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/runs/{run_slug}/resume-info")
def resume_info(req: ResumeInfoRequest, request: Request, run_slug: str) -> dict:
    return _resume_info_impl(req, request, run_slug)


@router.post(
    "/api/v1/sessions/resume-info",
    deprecated=True,
    summary="(Deprecated) Fetch resume info via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def resume_info_legacy(req: ResumeInfoRequest, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _resume_info_impl(req, request)


def _resume_session_impl(req: ResumeInfoRequest, request: Request, run_slug: str | None = None) -> dict:
    target_run_slug = run_slug or req.run_slug
    if target_run_slug is None:
        raise HTTPException(status_code=400, detail="run_slug_required")
    try:
        return request.app.state.session_service.resume_session(run_slug=target_run_slug, resume_token=req.resume_token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/runs/{run_slug}/resume")
def resume_session(req: ResumeInfoRequest, request: Request, run_slug: str) -> dict:
    return _resume_session_impl(req, request, run_slug)


@router.post(
    "/api/v1/sessions/resume",
    deprecated=True,
    summary="(Deprecated) Resume participant session via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def resume_session_legacy(req: ResumeInfoRequest, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _resume_session_impl(req, request)


def _start_session_impl(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/sessions/{session_id}/start")
def start_session(session_id: str, request: Request) -> dict:
    return _start_session_impl(session_id, request)


@router.post(
    "/api/v1/sessions/{session_id}/start",
    deprecated=True,
    summary="(Deprecated) Start participant session via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def start_session_legacy(session_id: str, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _start_session_impl(session_id, request)


def _session_progress_impl(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.get_progress_info(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/v1/public/sessions/{session_id}/progress")
def session_progress(session_id: str, request: Request) -> dict:
    return _session_progress_impl(session_id, request)


@router.get(
    "/api/v1/sessions/{session_id}/progress",
    deprecated=True,
    summary="(Deprecated) Get participant progress via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def session_progress_legacy(session_id: str, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _session_progress_impl(session_id, request)


def _final_submit_session_impl(session_id: str, request: Request) -> dict:
    try:
        return request.app.state.session_service.final_submit(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/sessions/{session_id}/final-submit")
def final_submit_session(session_id: str, request: Request) -> dict:
    return _final_submit_session_impl(session_id, request)


@router.post(
    "/api/v1/sessions/{session_id}/final-submit",
    deprecated=True,
    summary="(Deprecated) Final submit via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def final_submit_session_legacy(session_id: str, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _final_submit_session_impl(session_id, request)
