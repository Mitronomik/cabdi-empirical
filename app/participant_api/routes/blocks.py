from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from app.participant_api.routes.sessions import LEGACY_ALIAS_DEPRECATION_NOTE, _mark_legacy_alias

router = APIRouter(tags=["blocks"])


class BlockQuestionnaireRequest(BaseModel):
    burden: int
    trust: int
    usefulness: int


def _submit_block_questionnaire_impl(
    session_id: str,
    block_id: str,
    req: BlockQuestionnaireRequest,
    request: Request,
) -> dict:
    try:
        return request.app.state.trial_service.submit_block_questionnaire(session_id, block_id, req.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/v1/public/sessions/{session_id}/blocks/{block_id}/questionnaire")
def submit_block_questionnaire(session_id: str, block_id: str, req: BlockQuestionnaireRequest, request: Request) -> dict:
    return _submit_block_questionnaire_impl(session_id, block_id, req, request)


@router.post(
    "/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
    deprecated=True,
    summary="(Deprecated) Submit block questionnaire via legacy alias",
    description=LEGACY_ALIAS_DEPRECATION_NOTE,
)
def submit_block_questionnaire_legacy(
    session_id: str,
    block_id: str,
    req: BlockQuestionnaireRequest,
    request: Request,
    response: Response,
) -> dict:
    _mark_legacy_alias(response)
    return _submit_block_questionnaire_impl(session_id, block_id, req, request)
