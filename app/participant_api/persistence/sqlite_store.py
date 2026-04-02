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
                    assigned_order TEXT NOT NULL,
                    stimulus_set_map TEXT NOT NULL,
                    current_block_index INTEGER NOT NULL,
                    current_trial_index INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    device_info TEXT NOT NULL
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
                """
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
