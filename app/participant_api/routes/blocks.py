from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["blocks"])


class BlockQuestionnaireRequest(BaseModel):
    burden: int
    trust: int
    usefulness: int


@router.post("/api/v1/public/sessions/{session_id}/blocks/{block_id}/questionnaire")
@router.post("/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire")
def submit_block_questionnaire(session_id: str, block_id: str, req: BlockQuestionnaireRequest, request: Request) -> dict:
    try:
        return request.app.state.trial_service.submit_block_questionnaire(session_id, block_id, req.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
