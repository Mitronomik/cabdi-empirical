from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.participant_api.main import create_app
from app.participant_api.persistence.sqlite_store import SQLiteStore
from fastapi.testclient import TestClient


def _create_v1_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, 'create_initial_pilot_tables', datetime('now'));

            CREATE TABLE participant_sessions (
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

            CREATE TABLE session_trials (
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
                status TEXT NOT NULL
            );

            CREATE TABLE trial_event_logs (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                block_id TEXT NOT NULL,
                trial_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE trial_summary_logs (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                trial_id TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                UNIQUE(session_id, trial_id)
            );

            CREATE TABLE block_questionnaires (
                questionnaire_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                block_id TEXT NOT NULL,
                burden INTEGER,
                trust INTEGER,
                usefulness INTEGER,
                submitted_at TEXT NOT NULL,
                UNIQUE(session_id, block_id)
            );

            CREATE TABLE researcher_stimulus_sets (
                stimulus_set_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_family TEXT NOT NULL,
                source_format TEXT NOT NULL,
                n_items INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                items_json TEXT NOT NULL
            );

            CREATE TABLE researcher_runs (
                run_id TEXT PRIMARY KEY,
                run_name TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                task_family TEXT NOT NULL,
                config_json TEXT NOT NULL,
                stimulus_set_ids_json TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_fresh_bootstrap_creates_latest_schema_and_version_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "pilot.sqlite3"
    store = SQLiteStore(str(db_path))
    store.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()["version"]
        assert version == SQLiteStore.CURRENT_SCHEMA_VERSION
        run_id = conn.execute(
            "SELECT name, \"notnull\" FROM pragma_table_info('participant_sessions') WHERE name='run_id'"
        ).fetchone()
        assert run_id is not None
        assert int(run_id["notnull"]) == 1
    finally:
        conn.close()


def test_upgrade_from_v1_schema_applies_all_migrations(tmp_path: Path) -> None:
    db_path = tmp_path / "pilot_v1.sqlite3"
    _create_v1_schema(db_path)
    store = SQLiteStore(str(db_path))
    store.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert [int(row["version"]) for row in rows] == list(range(1, SQLiteStore.CURRENT_SCHEMA_VERSION + 1))
        participant_columns = {
            row["name"] for row in conn.execute("SELECT name FROM pragma_table_info('participant_sessions')").fetchall()
        }
        assert {"run_id", "public_session_code", "resume_token_hash", "language", "last_activity_at"}.issubset(
            participant_columns
        )
    finally:
        conn.close()


def test_unversioned_partial_legacy_schema_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_partial.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE participant_sessions (
                session_id TEXT PRIMARY KEY,
                participant_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                run_id TEXT,
                assigned_order TEXT NOT NULL,
                stimulus_set_map TEXT NOT NULL,
                current_block_index INTEGER NOT NULL,
                current_trial_index INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                device_info TEXT NOT NULL
            );
            CREATE TABLE session_trials (trial_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, block_id TEXT NOT NULL, block_index INTEGER NOT NULL, trial_index INTEGER NOT NULL, condition TEXT NOT NULL, stimulus_json TEXT NOT NULL, pre_render_features_json TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE trial_event_logs (event_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, block_id TEXT NOT NULL, trial_id TEXT NOT NULL, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL);
            CREATE TABLE trial_summary_logs (summary_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, trial_id TEXT NOT NULL, summary_json TEXT NOT NULL, UNIQUE(session_id, trial_id));
            CREATE TABLE block_questionnaires (questionnaire_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, block_id TEXT NOT NULL, burden INTEGER, trust INTEGER, usefulness INTEGER, submitted_at TEXT NOT NULL, UNIQUE(session_id, block_id));
            CREATE TABLE researcher_stimulus_sets (stimulus_set_id TEXT PRIMARY KEY, name TEXT NOT NULL, task_family TEXT NOT NULL, source_format TEXT NOT NULL, n_items INTEGER NOT NULL, created_at TEXT NOT NULL, items_json TEXT NOT NULL);
            CREATE TABLE researcher_runs (run_id TEXT PRIMARY KEY, run_name TEXT NOT NULL, experiment_id TEXT NOT NULL, task_family TEXT NOT NULL, config_json TEXT NOT NULL, stimulus_set_ids_json TEXT NOT NULL, notes TEXT, created_at TEXT NOT NULL);
            """
        )
        conn.commit()
    finally:
        conn.close()

    store = SQLiteStore(str(db_path))
    with pytest.raises(RuntimeError, match="partial legacy participant_sessions migration state"):
        store.init_db()


def test_participant_api_starts_on_migrated_database(tmp_path: Path) -> None:
    db_path = tmp_path / "pilot_v1.sqlite3"
    _create_v1_schema(db_path)
    store = SQLiteStore(str(db_path))
    store.init_db()

    client = TestClient(create_app(str(db_path)))
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
