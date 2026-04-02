"""FastAPI entrypoint for participant human-pilot API (PR-3 MVP)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.participant_api.persistence.sqlite_store import SQLiteStore
from app.participant_api.routes import blocks, exports, health, sessions, trials
from app.participant_api.services.export_service import ExportService
from app.participant_api.services.session_service import SessionService
from app.participant_api.services.trial_service import TrialService


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="CABDI Pilot Participant API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = SQLiteStore(db_path or os.getenv("PILOT_DB_PATH", "pilot/sessions/pilot_sessions.sqlite3"))
    store.init_db()
    session_service = SessionService(store)
    trial_service = TrialService(store, session_service)
    export_service = ExportService(store)

    app.state.store = store
    app.state.session_service = session_service
    app.state.trial_service = trial_service
    app.state.export_service = export_service

    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(trials.router)
    app.include_router(blocks.router)
    app.include_router(exports.router)
    return app


app = create_app()