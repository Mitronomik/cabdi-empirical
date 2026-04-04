from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

router = APIRouter(prefix="/admin/api/v1/stimuli", tags=["admin-stimuli"])


@router.post("/upload")
async def upload_stimuli(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    source_format: str = Form(...),
) -> dict:
    payload = await file.read()
    try:
        return request.app.state.stimulus_service.upload_stimulus_set(
            name=name,
            content=payload,
            source_format=source_format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_stimuli(request: Request) -> list[dict]:
    return request.app.state.stimulus_service.list_stimulus_sets()


@router.get("/{stimulus_set_id}")
def get_stimulus_set(stimulus_set_id: str, request: Request) -> dict:
    try:
        return request.app.state.stimulus_service.get_stimulus_set(stimulus_set_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
