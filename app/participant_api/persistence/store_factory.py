"""Persistence backend selection for pilot APIs."""

from __future__ import annotations

import os

from app.participant_api.persistence.postgres_store import PostgresStore
from app.participant_api.persistence.sqlite_store import SQLiteStore
from app.participant_api.persistence.store_protocol import PilotStore

DEFAULT_SQLITE_PATH = "pilot/sessions/pilot_sessions.sqlite3"


def create_store(db_target: str | None = None) -> PilotStore:
    resolved = (db_target or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH") or DEFAULT_SQLITE_PATH).strip()
    if resolved.startswith(("postgres://", "postgresql://")):
        return PostgresStore(resolved)
    if resolved.startswith("sqlite:///"):
        return SQLiteStore(resolved.replace("sqlite:///", "", 1))
    return SQLiteStore(resolved)
