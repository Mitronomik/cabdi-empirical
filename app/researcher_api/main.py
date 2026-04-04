"""FastAPI entrypoint for researcher/admin pilot API (PR-5 MVP)."""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.participant_api.persistence.store_factory import create_store
from app.researcher_api.routes import admin_runs, diagnostics, exports, stimuli
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.export_service import AdminExportService
from app.researcher_api.services.run_service import RunService
from app.researcher_api.services.stimulus_service import StimulusService


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="CABDI Pilot Researcher Admin API", version="0.1.0")

    db_target = db_path or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH")
    store = create_store(db_target)
    store.init_db()

    app.state.store = store
    app.state.stimulus_service = StimulusService(store)
    app.state.run_service = RunService(store)
    app.state.diagnostics_service = DiagnosticsService(store)
    app.state.admin_export_service = AdminExportService(store)

    app.include_router(stimuli.router)
    app.include_router(admin_runs.router)
    app.include_router(diagnostics.router)
    app.include_router(exports.router)
    return app


app = create_app()
