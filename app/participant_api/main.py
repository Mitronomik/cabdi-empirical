"""FastAPI entrypoint for participant human-pilot API (PR-3 MVP)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.participant_api.persistence.store_factory import create_store
from app.participant_api.routes import blocks, exports, health, public_runs, sessions, trials
from app.participant_api.services.export_service import ExportService
from app.participant_api.services.session_service import SessionService
from app.participant_api.services.trial_service import TrialService

LOCAL_PARTICIPANT_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)
PRODUCTION_LIKE_ENVS = {"prod", "production", "staging"}


def _is_production_like_env() -> bool:
    return os.getenv("PILOT_ENV", "local").strip().lower() in PRODUCTION_LIKE_ENVS


def _resolve_allowed_origins() -> list[str]:
    configured = os.getenv("PILOT_PARTICIPANT_CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if _is_production_like_env():
        raise RuntimeError(
            "Missing PILOT_PARTICIPANT_CORS_ORIGINS in production-like mode. "
            "Set explicit participant web origins (comma-separated)."
        )
    return list(LOCAL_PARTICIPANT_ORIGINS)


def _resolve_db_target(db_path: str | None) -> str | None:
    resolved = db_path or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH")
    if _is_production_like_env():
        if not os.getenv("PILOT_DB_URL"):
            raise RuntimeError("Missing PILOT_DB_URL in production-like mode for deployment packaging.")
        if not str(os.getenv("PILOT_DB_URL", "")).startswith(("postgres://", "postgresql://")):
            raise RuntimeError("PILOT_DB_URL must be a Postgres URL in production-like mode.")
    return resolved


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="CABDI Pilot Participant API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = create_store(_resolve_db_target(db_path))
    store.init_db()
    session_service = SessionService(store)
    trial_service = TrialService(store, session_service)
    export_service = ExportService(store)

    app.state.store = store
    app.state.session_service = session_service
    app.state.trial_service = trial_service
    app.state.export_service = export_service

    app.include_router(health.router)
    app.include_router(public_runs.router)
    app.include_router(sessions.router)
    app.include_router(trials.router)
    app.include_router(blocks.router)
    app.include_router(exports.router)
    return app


app = create_app()
