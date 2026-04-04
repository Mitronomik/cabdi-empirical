from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.researcher_api.auth import require_researcher_auth

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-runs"], dependencies=[Depends(require_researcher_auth)])


class CreateRunRequest(BaseModel):
    run_name: str
    public_slug: str | None = None
    experiment_id: str
    task_family: str
    config: dict[str, Any]
    stimulus_set_ids: list[str]
    notes: str | None = None


class CloseRunRequest(BaseModel):
    confirm_run_id: str


@router.post("")
def create_run(req: CreateRunRequest, request: Request) -> dict:
    try:
        return request.app.state.run_service.create_run(
            run_name=req.run_name,
            public_slug=req.public_slug,
            experiment_id=req.experiment_id,
            task_family=req.task_family,
            config=req.config,
            stimulus_set_ids=req.stimulus_set_ids,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/defaults")
def run_builder_defaults(request: Request) -> dict:
    return request.app.state.run_service.get_run_builder_defaults()


@router.get("")
def list_runs(request: Request) -> list[dict]:
    return request.app.state.run_service.list_runs()


@router.get("/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.run_service.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/sessions")
def run_sessions(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.run_service.list_run_sessions(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/activate")
def activate_run(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.run_service.activate_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{run_id}/pause")
def pause_run(run_id: str, request: Request) -> dict:
    try:
        return request.app.state.run_service.pause_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{run_id}/close")
def close_run(run_id: str, req: CloseRunRequest, request: Request) -> dict:
    if req.confirm_run_id != run_id:
        raise HTTPException(
            status_code=400,
            detail="close_run requires explicit confirm_run_id equal to run_id",
        )
    try:
        return request.app.state.run_service.close_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
