from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from app.participant_api.routes.sessions import LEGACY_ALIAS_DEPRECATION_NOTE, _mark_legacy_alias

router = APIRouter(tags=["trials"])


class TrialEventInput(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SubmitTrialRequest(BaseModel):
    human_response: str
    reaction_time_ms: int
    self_confidence: int = Field(ge=1, le=4)
    reason_clicked: bool = False
    evidence_opened: bool = False
    verification_completed: bool = False
    event_trace: list[TrialEventInput] | None = None


def _next_trial_impl(session_id: str, request: Request) -> dict:
    try:
        trial = request.app.state.trial_service.next_trial(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc).startswith("block_questionnaire_required:"):
            block_id = str(exc).split(":", 1)[1]
            raise HTTPException(status_code=409, detail={"message": "block_questionnaire_required", "block_id": block_id}) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if trial is None:
        return {"status": "in_progress"}
    return trial


@router.get("/api/v1/public/sessions/{session_id}/next-trial")
def next_trial(session_id: str, request: Request) -> dict:
    return _next_trial_impl(session_id, request)


@router.get(
    "/api/v1/sessions/{session_id}/next-trial",
    deprecated=True,
    summary="(Deprecated) Fetch next trial via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def next_trial_legacy(session_id: str, request: Request, response: Response) -> dict:
    _mark_legacy_alias(response)
    return _next_trial_impl(session_id, request)


def _submit_trial_impl(session_id: str, trial_id: str, req: SubmitTrialRequest, request: Request) -> dict:
    try:
        return request.app.state.trial_service.submit_trial(session_id, trial_id, req.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/sessions/{session_id}/trials/{trial_id}/submit")
def submit_trial(session_id: str, trial_id: str, req: SubmitTrialRequest, request: Request) -> dict:
    return _submit_trial_impl(session_id, trial_id, req, request)


@router.post(
    "/api/v1/sessions/{session_id}/trials/{trial_id}/submit",
    deprecated=True,
    summary="(Deprecated) Submit trial via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def submit_trial_legacy(
    session_id: str,
    trial_id: str,
    req: SubmitTrialRequest,
    request: Request,
    response: Response,
) -> dict:
    _mark_legacy_alias(response)
    return _submit_trial_impl(session_id, trial_id, req, request)
