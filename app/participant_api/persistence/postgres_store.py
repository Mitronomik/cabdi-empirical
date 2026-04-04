"""Postgres-backed pilot persistence with migration parity."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - guarded by runtime backend selection
    psycopg = None
    dict_row = None


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[Any], None]


class PostgresStore:
    CURRENT_SCHEMA_VERSION = 6

    def __init__(self, db_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("Postgres backend requires psycopg. Install requirements and retry.")
        self.db_url = db_url

    @contextmanager
    def connect(self) -> Iterator[Any]:
        conn = psycopg.connect(self.db_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _adapt_query(self, query: str) -> str:
        return query.replace("?", "%s")

    def init_db(self) -> None:
        with self.connect() as conn:
            self._ensure_migration_table(conn)
            current_version = self._current_schema_version(conn)
            if current_version is None:
                if self._has_non_migration_tables(conn):
                    raise RuntimeError(
                        "Detected unversioned Postgres schema with pilot tables but no schema_migrations history. "
                        "Run explicit migration tooling to reconcile schema state."
                    )
                current_version = 0
            if current_version > self.CURRENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {current_version} is newer than supported {self.CURRENT_SCHEMA_VERSION}."
                )
            for migration in self._migrations():
                if migration.version > current_version:
                    migration.apply(conn)
                    conn.execute(
                        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (%s, %s, %s)",
                        (migration.version, migration.name, _now_iso()),
                    )
                    current_version = migration.version
            self._validate_current_schema(conn)

    @property
    def schema_version(self) -> int:
        return self.CURRENT_SCHEMA_VERSION

    def placeholders(self, n: int) -> str:
        return ", ".join("%s" for _ in range(n))

    def transaction(self) -> Iterator[Any]:
        return self.connect()

    def _migrations(self) -> list[Migration]:
        return [
            Migration(1, "create_initial_pilot_tables", self._migration_001_create_initial_tables),
            Migration(2, "add_session_resume_and_run_columns", self._migration_002_add_session_columns),
            Migration(3, "add_run_slug_and_status_columns", self._migration_003_add_run_columns),
            Migration(4, "add_stimulus_validation_columns", self._migration_004_add_stimulus_validation_columns),
            Migration(5, "enforce_participant_session_run_not_null", self._migration_005_enforce_run_not_null),
            Migration(6, "add_researcher_users_table", self._migration_006_add_researcher_users_table),
        ]

    def _ensure_migration_table(self, conn: Any) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _current_schema_version(self, conn: Any) -> int | None:
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

    def _has_non_migration_tables(self, conn: Any) -> bool:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_type = 'BASE TABLE'
              AND table_name <> 'schema_migrations'
            """
        ).fetchone()
        return int(row["n"]) > 0

    def _validate_current_schema(self, conn: Any) -> None:
        version = self._current_schema_version(conn)
        if version != self.CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} does not match required {self.CURRENT_SCHEMA_VERSION} after migration."
            )
        row = conn.execute(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'participant_sessions'
              AND column_name = 'run_id'
            """
        ).fetchone()
        if row is None or str(row["is_nullable"]).upper() != "NO":
            raise RuntimeError("participant_sessions.run_id must be NOT NULL in Postgres schema.")

    def _migration_001_create_initial_tables(self, conn: Any) -> None:
        conn.execute(
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
            )
            """
        )
        conn.execute(
            """
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
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE trial_event_logs (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                block_id TEXT NOT NULL,
                trial_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE trial_summary_logs (
                summary_id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                trial_id TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                UNIQUE(session_id, trial_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE block_questionnaires (
                questionnaire_id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                block_id TEXT NOT NULL,
                burden INTEGER,
                trust INTEGER,
                usefulness INTEGER,
                submitted_at TEXT NOT NULL,
                UNIQUE(session_id, block_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE researcher_stimulus_sets (
                stimulus_set_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_family TEXT NOT NULL,
                source_format TEXT NOT NULL,
                n_items INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                items_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE researcher_runs (
                run_id TEXT PRIMARY KEY,
                run_name TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                task_family TEXT NOT NULL,
                config_json TEXT NOT NULL,
                stimulus_set_ids_json TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

    def _migration_002_add_session_columns(self, conn: Any) -> None:
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN run_id TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN public_session_code TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN resume_token_hash TEXT")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
        conn.execute("ALTER TABLE participant_sessions ADD COLUMN last_activity_at TEXT")

    def _migration_003_add_run_columns(self, conn: Any) -> None:
        conn.execute("ALTER TABLE researcher_runs ADD COLUMN public_slug TEXT")
        conn.execute("ALTER TABLE researcher_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
        conn.execute("CREATE UNIQUE INDEX idx_researcher_runs_public_slug ON researcher_runs(public_slug)")

    def _migration_004_add_stimulus_validation_columns(self, conn: Any) -> None:
        conn.execute(
            "ALTER TABLE researcher_stimulus_sets ADD COLUMN validation_status TEXT NOT NULL DEFAULT 'invalid'"
        )
        conn.execute(
            "ALTER TABLE researcher_stimulus_sets ADD COLUMN payload_schema_version TEXT NOT NULL DEFAULT 'stimulus_payload.v1'"
        )
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '[]'")
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN errors_json TEXT NOT NULL DEFAULT '[]'")
        conn.execute("ALTER TABLE researcher_stimulus_sets ADD COLUMN preview_rows_json TEXT NOT NULL DEFAULT '[]'")

    def _migration_005_enforce_run_not_null(self, conn: Any) -> None:
        null_run_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM participant_sessions WHERE run_id IS NULL OR btrim(run_id) = ''"
        ).fetchone()["n"]
        if int(null_run_rows) > 0:
            raise RuntimeError(
                "Cannot enforce participant_sessions.run_id NOT NULL: found existing rows with NULL/empty run_id."
            )
        conn.execute("ALTER TABLE participant_sessions ALTER COLUMN run_id SET NOT NULL")

    def _migration_006_add_researcher_users_table(self, conn: Any) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS researcher_users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

    def fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(self._adapt_query(query), params).fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(self._adapt_query(query), params).fetchall()
            return [dict(row) for row in rows]

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self.connect() as conn:
            conn.execute(self._adapt_query(query), params)

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> None:
        with self.connect() as conn:
            conn.executemany(self._adapt_query(query), params)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
