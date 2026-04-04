from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/admin/api/v1/runs", tags=["admin-runs"])


class CreateRunRequest(BaseModel):
    run_name: str
    public_slug: str | None = None
    experiment_id: str
    task_family: str
    config: dict[str, Any]
    stimulus_set_ids: list[str]
    notes: str | None = None


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
