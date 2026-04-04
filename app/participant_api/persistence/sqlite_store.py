"""SQLite-backed MVP persistence for participant pilot API."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class SQLiteStore:
    """Thin persistence wrapper with explicit SQL for easy migration later."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS participant_sessions (
                    session_id TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    assigned_order TEXT NOT NULL,
                    stimulus_set_map TEXT NOT NULL,
                    current_block_index INTEGER NOT NULL,
                    current_trial_index INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_activity_at TEXT,
                    device_info TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT "en"
                );

                CREATE TABLE IF NOT EXISTS session_trials (
                    trial_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    block_id TEXT NOT NULL,
                    block_index INTEGER NOT NULL,
                    trial_index INTEGER NOT NULL,
                    condition TEXT NOT NULL,
                    stimulus_json TEXT NOT NULL,
                    pre_render_features_json TEXT NOT NULL,
                    risk_bucket TEXT,
                    policy_decision_json TEXT,
                    served_at TEXT,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES participant_sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS trial_event_logs (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    block_id TEXT NOT NULL,
                    trial_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trial_summary_logs (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trial_id TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    UNIQUE(session_id, trial_id)
                );

                CREATE TABLE IF NOT EXISTS block_questionnaires (
                    questionnaire_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    block_id TEXT NOT NULL,
                    burden INTEGER,
                    trust INTEGER,
                    usefulness INTEGER,
                    submitted_at TEXT NOT NULL,
                    UNIQUE(session_id, block_id)
                );

                CREATE TABLE IF NOT EXISTS researcher_stimulus_sets (
                    stimulus_set_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    task_family TEXT NOT NULL,
                    source_format TEXT NOT NULL,
                    n_items INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    items_json TEXT NOT NULL,
                    validation_status TEXT NOT NULL DEFAULT 'invalid',
                    payload_schema_version TEXT NOT NULL DEFAULT 'stimulus_payload.v1',
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    preview_rows_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS researcher_runs (
                    run_id TEXT PRIMARY KEY,
                    run_name TEXT NOT NULL,
                    public_slug TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    experiment_id TEXT NOT NULL,
                    task_family TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    stimulus_set_ids_json TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "participant_sessions", "run_id", "TEXT")
            self._ensure_column(conn, "participant_sessions", "language", "TEXT NOT NULL DEFAULT 'en'")
            self._ensure_column(conn, "participant_sessions", "last_activity_at", "TEXT")
            self._ensure_column(conn, "researcher_runs", "public_slug", "TEXT")
            self._ensure_column(conn, "researcher_runs", "status", "TEXT NOT NULL DEFAULT 'draft'")
            self._ensure_column(
                conn,
                "researcher_stimulus_sets",
                "validation_status",
                "TEXT NOT NULL DEFAULT 'invalid'",
            )
            self._ensure_column(
                conn,
                "researcher_stimulus_sets",
                "payload_schema_version",
                "TEXT NOT NULL DEFAULT 'stimulus_payload.v1'",
            )
            self._ensure_column(
                conn,
                "researcher_stimulus_sets",
                "warnings_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                conn,
                "researcher_stimulus_sets",
                "errors_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                conn,
                "researcher_stimulus_sets",
                "preview_rows_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._assert_not_null_column(conn, "participant_sessions", "run_id")

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def _assert_not_null_column(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> None:
        column_rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        for row in column_rows:
            if row["name"] == column_name and int(row["notnull"]) != 1:
                raise RuntimeError(
                    f"{table_name}.{column_name} must be NOT NULL; recreate local DB or migrate schema before running service"
                )

    def fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self.connect() as conn:
            conn.execute(query, params)

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> None:
        with self.connect() as conn:
            conn.executemany(query, params)


def dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True)


def loads(payload: str) -> Any:
    return json.loads(payload)
