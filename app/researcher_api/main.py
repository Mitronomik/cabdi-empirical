"""FastAPI entrypoint for researcher/admin pilot API (PR-5 MVP)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.participant_api.persistence.store_factory import create_store
from app.researcher_api.routes import admin_runs, auth, diagnostics, exports, stimuli
from app.researcher_api.services.auth_service import AuthService
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.export_service import AdminExportService
from app.researcher_api.services.run_service import RunService
from app.researcher_api.services.stimulus_service import StimulusService


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="CABDI Pilot Researcher Admin API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    env_mode = os.getenv("PILOT_ENV", "local").strip().lower()
    session_secret = os.getenv("PILOT_RESEARCHER_SESSION_SECRET")
    if not session_secret:
        if env_mode in {"prod", "production", "staging"}:
            raise RuntimeError(
                "Missing PILOT_RESEARCHER_SESSION_SECRET in production-like mode for researcher/admin auth."
            )
        session_secret = "dev-only-insecure-session-secret-change-me"
    db_target = db_path or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH")
    store = create_store(db_target)
    store.init_db()

    app.state.store = store
    app.state.stimulus_service = StimulusService(store)
    app.state.run_service = RunService(store)
    app.state.diagnostics_service = DiagnosticsService(store)
    app.state.admin_export_service = AdminExportService(store)
    app.state.auth_service = AuthService(store)
    app.state.researcher_session_secret = session_secret
    app.state.auth_service.bootstrap_initial_user()

    app.include_router(auth.router)
    app.include_router(stimuli.router)
    app.include_router(admin_runs.router)
    app.include_router(diagnostics.router)
    app.include_router(exports.router)
    return app


app = create_app()
