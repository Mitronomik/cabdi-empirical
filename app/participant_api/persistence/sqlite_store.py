"""SQLite-backed MVP persistence for participant pilot API."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


class SQLiteStore:
    """SQLite-backed persistence with explicit schema migration ownership."""

    CURRENT_SCHEMA_VERSION = 5

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
            self._ensure_migration_table(conn)
            current_version = self._current_schema_version(conn)
            if current_version is None:
                current_version = self._infer_legacy_schema_version(conn)
                if current_version > 0:
                    self._record_inferred_legacy_versions(conn, current_version)
            if current_version > self.CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {current_version} is newer than supported {self.CURRENT_SCHEMA_VERSION}."
                )
            for migration in self._migrations():
                if migration.version > current_version:
                    migration.apply(conn)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, datetime('now'))",
                        (migration.version, migration.name),
                    )
                    current_version = migration.version
            self._validate_current_schema(conn)

    def _assert_not_null_column(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> None:
        column_rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        for row in column_rows:
            if row["name"] == column_name:
                if int(row["notnull"]) != 1:
                    raise RuntimeError(
                        f"{table_name}.{column_name} must be NOT NULL; recreate local DB or migrate schema before running service"
                    )
                return
        raise RuntimeError(f"{table_name}.{column_name} is missing; local DB schema is incompatible with current service.")

    def _migrations(self) -> list[Migration]:
        return [
            Migration(1, "create_initial_pilot_tables", self._migration_001_create_initial_tables),
            Migration(2, "add_session_resume_and_run_columns", self._migration_002_add_session_columns),
            Migration(3, "add_run_slug_and_status_columns", self._migration_003_add_run_columns),
            Migration(4, "add_stimulus_validation_columns", self._migration_004_add_stimulus_validation_columns),
            Migration(5, "enforce_participant_session_run_not_null", self._migration_005_enforce_run_not_null),
        ]

    def _ensure_migration_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _current_schema_version(self, conn: sqlite3.Connection) -> int | None:
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        if not rows:
            return None
        versions = [int(row["version"]) for row in rows]
        expected = list(range(1, versions[-1] + 1))
        if versions != expected:
            raise RuntimeError(
                f"Detected non-contiguous schema_migrations history: {versions}; expected {expected}. "
                "Refusing startup until schema history is repaired."
            )
        return versions[-1]

    def _infer_legacy_schema_version(self, conn: sqlite3.Connection) -> int:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        }
        non_migration_tables = tables - {"schema_migrations"}
        if not non_migration_tables:
            return 0
        required_base_tables = {
            "participant_sessions",
            "session_trials",
            "trial_event_logs",
            "trial_summary_logs",
            "block_questionnaires",
            "researcher_stimulus_sets",
            "researcher_runs",
        }
        if not required_base_tables.issubset(non_migration_tables):
            missing = sorted(required_base_tables - non_migration_tables)
            raise RuntimeError(
                "Detected unversioned legacy database with missing required pilot tables: "
                f"{missing}. Refusing implicit schema repair."
            )
        version = 1
        participant_columns = self._table_columns(conn, "participant_sessions")
        if self._all_columns_present(
            participant_columns, {"run_id", "public_session_code", "resume_token_hash", "language", "last_activity_at"}
        ):
            version = 2
        elif self._any_columns_present(
            participant_columns, {"run_id", "public_session_code", "resume_token_hash", "language", "last_activity_at"}
        ):
            raise RuntimeError(
                "Detected partial legacy participant_sessions migration state in unversioned DB. "
                "Run explicit migration tooling or recreate DB."
            )
        run_columns = self._table_columns(conn, "researcher_runs")
        if self._all_columns_present(run_columns, {"public_slug", "status"}):
            version = 3
        elif self._any_columns_present(run_columns, {"public_slug", "status"}):
            raise RuntimeError(
                "Detected partial legacy researcher_runs migration state in unversioned DB. "
                "Run explicit migration tooling or recreate DB."
            )
        stimulus_columns = self._table_columns(conn, "researcher_stimulus_sets")
        stimulus_added = {
            "validation_status",
            "payload_schema_version",
            "warnings_json",
            "errors_json",
            "preview_rows_json",
        }
        if self._all_columns_present(stimulus_columns, stimulus_added):
            version = 4
        elif self._any_columns_present(stimulus_columns, stimulus_added):
            raise RuntimeError(
                "Detected partial legacy researcher_stimulus_sets migration state in unversioned DB. "
                "Run explicit migration tooling or recreate DB."
            )
        if version >= 2 and self._column_is_not_null(conn, "participant_sessions", "run_id"):
            version = 5
        return version

    def _record_inferred_legacy_versions(self, conn: sqlite3.Connection, version: int) -> None:
        names = {migration.version: migration.name for migration in self._migrations()}
        for index in range(1, version + 1):
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, datetime('now'))",
                (index, f"{names[index]}:legacy_inferred"),
            )

    def _validate_current_schema(self, conn: sqlite3.Connection) -> None:
        version = self._current_schema_version(conn)
        if version != self.CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} does not match required {self.CURRENT_SCHEMA_VERSION} after migration."
            )
        self._assert_not_null_column(conn, "participant_sessions", "run_id")

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> dict[str, sqlite3.Row]:
        return {row["name"]: row for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}

    def _all_columns_present(self, columns: dict[str, sqlite3.Row], required: set[str]) -> bool:
        return required.issubset(columns.keys())

    def _any_columns_present(self, columns: dict[str, sqlite3.Row], required: set[str]) -> bool:
        return bool(required.intersection(columns.keys()))

    def _column_is_not_null(self, conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        columns = self._table_columns(conn, table_name)
        column = columns.get(column_name)
        if column is None:
            return False
        return int(column["notnull"]) == 1

    def _migration_001_create_initial_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
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
                status TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES participant_sessions(session_id)
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

    def _migration_002_add_session_columns(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN run_id TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN public_session_code TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN resume_token_hash TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN last_activity_at TEXT")

    def _migration_003_add_run_columns(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE researcher_runs ADD COLUMN public_slug TEXT")
        conn.execute("ALTER TABLE researcher_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        conn.execute("CREATE UNIQUE INDEX idx_researcher_runs_public_slug ON researcher_runs(public_slug)")

    def _migration_004_add_stimulus_validation_columns(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "ALTER TABLE researcher_stimulus_sets ADD COLUMN validation_status TEXT NOT NULL DEFAULT 'invalid'"
        )
        conn.execute(
            "ALTER TABLE researcher_stimulus_sets ADD COLUMN payload_schema_version TEXT NOT NULL DEFAULT 'stimulus_payload.v1'"
        )
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '[]'")
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN errors_json TEXT NOT NULL DEFAULT '[]'")
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN preview_rows_json TEXT NOT NULL DEFAULT '[]'")

    def _migration_005_enforce_run_not_null(self, conn: sqlite3.Connection) -> None:
        null_run_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM participant_sessions WHERE run_id IS NULL OR trim(run_id) = ''"
        ).fetchone()["n"]
        if int(null_run_rows) > 0:
            raise RuntimeError(
                "Cannot enforce participant_sessions.run_id NOT NULL: found existing rows with NULL/empty run_id."
            )
        conn.executescript(
            """
            CREATE TABLE participant_sessions_new (
                session_id TEXT PRIMARY KEY,
                participant_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                public_session_code TEXT,
                resume_token_hash TEXT,
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

            INSERT INTO participant_sessions_new(
                session_id, participant_id, experiment_id, run_id, public_session_code, resume_token_hash,
                assigned_order, stimulus_set_map, current_block_index, current_trial_index,
                status, started_at, completed_at, last_activity_at, device_info, language
            )
            SELECT
                session_id, participant_id, experiment_id, run_id, public_session_code, resume_token_hash,
                assigned_order, stimulus_set_map, current_block_index, current_trial_index,
                status, started_at, completed_at, last_activity_at, device_info, language
            FROM participant_sessions;

            DROP TABLE participant_sessions;
            ALTER TABLE participant_sessions_new RENAME TO participant_sessions;
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
