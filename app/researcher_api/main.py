"""FastAPI entrypoint for researcher/admin pilot API (PR-5 MVP)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.participant_api.persistence.store_factory import create_store
from app.researcher_api.routes import (
    admin_runs,
    auth,
    dashboard,
    diagnostics,
    exports,
    health,
    stimuli,
)
from app.researcher_api.services.auth_service import AuthService
from app.researcher_api.services.dashboard_service import DashboardService
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.export_service import AdminExportService
from app.researcher_api.services.run_service import RunService
from app.researcher_api.services.stimulus_service import StimulusService

LOCAL_RESEARCHER_ORIGINS = ("http://127.0.0.1:5174", "http://localhost:5174")
PRODUCTION_LIKE_ENVS = {"prod", "production", "staging"}
MIN_SESSION_SECRET_LENGTH = 32
INSECURE_SESSION_SECRET_MARKERS = ("change-me", "insecure", "example", "placeholder", "dev-only")


def _is_production_like_env() -> bool:
    return os.getenv("PILOT_ENV", "local").strip().lower() in PRODUCTION_LIKE_ENVS


def _resolve_allowed_origins() -> list[str]:
    configured = os.getenv("PILOT_RESEARCHER_CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    if _is_production_like_env():
        raise RuntimeError(
            "Missing PILOT_RESEARCHER_CORS_ORIGINS in production-like mode. "
            "Set explicit researcher web origins (comma-separated)."
        )
    return list(LOCAL_RESEARCHER_ORIGINS)


def _resolve_db_target(db_path: str | None) -> str | None:
    resolved = db_path or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH")
    if _is_production_like_env():
        db_url = os.getenv("PILOT_DB_URL", "")
        if not db_url:
            raise RuntimeError(
                "Missing PILOT_DB_URL in production-like mode for deployment packaging."
            )
        if not db_url.startswith(("postgres://", "postgresql://")):
            raise RuntimeError("PILOT_DB_URL must be a Postgres URL in production-like mode.")
    return resolved


def _resolve_cookie_security() -> bool:
    secure_override = os.getenv("PILOT_RESEARCHER_COOKIE_SECURE")
    if _is_production_like_env():
        if secure_override is None:
            raise RuntimeError(
                "Missing PILOT_RESEARCHER_COOKIE_SECURE in production-like mode. "
                "Set it explicitly to true for launch-facing researcher/admin deployment."
            )
        if secure_override.strip().lower() not in {"1", "true", "yes", "on"}:
            raise RuntimeError(
                "PILOT_RESEARCHER_COOKIE_SECURE must be true in production-like mode."
            )
        return True
    if secure_override is not None:
        return secure_override.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _resolve_export_root() -> str:
    return os.getenv("PILOT_EXPORT_ARTIFACT_ROOT", "artifacts/pilot_exports")


def _resolve_participant_base_url() -> str:
    return os.getenv("PILOT_PARTICIPANT_BASE_URL", "http://localhost:5173").rstrip("/")


def _is_insecure_session_secret(secret: str) -> bool:
    normalized = secret.strip().lower()
    if len(secret) < MIN_SESSION_SECRET_LENGTH:
        return True
    if normalized in {"secret", "changeme", "change-me", "password", "researcher-session-secret"}:
        return True
    return any(marker in normalized for marker in INSECURE_SESSION_SECRET_MARKERS)


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="CABDI Pilot Researcher Admin API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    allowed_origins = _resolve_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    env_mode = os.getenv("PILOT_ENV", "local").strip().lower()
    session_secret = os.getenv("PILOT_RESEARCHER_SESSION_SECRET")
    if not session_secret:
        if env_mode in PRODUCTION_LIKE_ENVS:
            raise RuntimeError(
                "Missing PILOT_RESEARCHER_SESSION_SECRET in production-like mode for researcher/admin auth."
            )
        session_secret = "dev-only-insecure-session-secret-change-me"
    elif env_mode in PRODUCTION_LIKE_ENVS and _is_insecure_session_secret(session_secret):
        raise RuntimeError(
            "PILOT_RESEARCHER_SESSION_SECRET is insecure for production-like mode. "
            "Use a high-entropy secret with at least 32 characters and no placeholder text."
        )

    store = create_store(_resolve_db_target(db_path))
    store.init_db()

    app.state.store = store
    app.state.stimulus_service = StimulusService(store)
    app.state.run_service = RunService(store, participant_base_url=_resolve_participant_base_url())
    app.state.diagnostics_service = DiagnosticsService(store)
    app.state.admin_export_service = AdminExportService(store, export_root=_resolve_export_root())
    app.state.dashboard_service = DashboardService(
        run_service=app.state.run_service,
        diagnostics_service=app.state.diagnostics_service,
        export_service=app.state.admin_export_service,
    )
    app.state.auth_service = AuthService(store)
    app.state.researcher_session_secret = session_secret
    app.state.researcher_cookie_secure = _resolve_cookie_security()
    app.state.researcher_cookie_samesite = "strict" if env_mode in PRODUCTION_LIKE_ENVS else "lax"
    app.state.researcher_allowed_origins = tuple(allowed_origins)
    app.state.auth_service.bootstrap_initial_user()

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(stimuli.router)
    app.include_router(admin_runs.router)
    app.include_router(diagnostics.router)
    app.include_router(exports.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
