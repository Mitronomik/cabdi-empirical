"""Repository-owned backup/restore helpers for pilot operational safety."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.participant_api.persistence.store_factory import create_store

BACKUP_FORMAT_VERSION = 1


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec("schema_migrations", ("version", "name", "applied_at"), ("version",)),
    TableSpec(
        "researcher_users",
        ("user_id", "username", "password_hash", "is_admin", "is_active", "created_at"),
        ("created_at", "user_id"),
    ),
    TableSpec(
        "researcher_stimulus_sets",
        (
            "stimulus_set_id",
            "name",
            "task_family",
            "source_format",
            "n_items",
            "created_at",
            "items_json",
            "validation_status",
            "payload_schema_version",
            "warnings_json",
            "errors_json",
            "preview_rows_json",
        ),
        ("created_at", "stimulus_set_id"),
    ),
    TableSpec(
        "researcher_runs",
        (
            "run_id",
            "run_name",
            "public_slug",
            "status",
            "experiment_id",
            "task_family",
            "config_json",
            "stimulus_set_ids_json",
            "notes",
            "created_at",
        ),
        ("created_at", "run_id"),
    ),
    TableSpec(
        "participant_sessions",
        (
            "session_id",
            "participant_id",
            "experiment_id",
            "run_id",
            "public_session_code",
            "resume_token_hash",
            "assigned_order",
            "stimulus_set_map",
            "current_block_index",
            "current_trial_index",
            "status",
            "started_at",
            "completed_at",
            "last_activity_at",
            "device_info",
            "language",
        ),
        ("started_at", "session_id"),
    ),
    TableSpec(
        "session_trials",
        (
            "trial_id",
            "session_id",
            "block_id",
            "block_index",
            "trial_index",
            "condition",
            "stimulus_json",
            "pre_render_features_json",
            "risk_bucket",
            "policy_decision_json",
            "served_at",
            "completed_at",
            "status",
        ),
        ("session_id", "block_index", "trial_index", "trial_id"),
    ),
    TableSpec(
        "trial_event_logs",
        ("event_id", "session_id", "block_id", "trial_id", "timestamp", "event_type", "payload_json"),
        ("timestamp", "event_id"),
    ),
    TableSpec("trial_summary_logs", ("summary_id", "session_id", "trial_id", "summary_json"), ("summary_id",)),
    TableSpec(
        "block_questionnaires",
        ("questionnaire_id", "session_id", "block_id", "burden", "trust", "usefulness", "submitted_at"),
        ("questionnaire_id",),
    ),
)


class BackupRestoreError(RuntimeError):
    """Raised when backup or restore conditions are invalid."""



def backup_database(*, db_target: str, output_path: str) -> dict[str, Any]:
    store = create_store(db_target)
    store.init_db()
    schema_version = _required_schema_version(store)
    rows_by_table: dict[str, list[dict[str, Any]]] = {}
    row_counts: dict[str, int] = {}
    for spec in TABLE_SPECS:
        query = (
            f"SELECT {', '.join(spec.columns)} FROM {spec.name} "
            f"ORDER BY {', '.join(spec.order_by)}"
        )
        rows = store.fetchall(query, ())
        rows_by_table[spec.name] = rows
        row_counts[spec.name] = len(rows)

    payload = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "schema_version": schema_version,
        "created_at": _utc_now(),
        "db_target_type": "postgres" if db_target.startswith(("postgres://", "postgresql://")) else "sqlite",
        "tables": rows_by_table,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return {"output_path": str(out), "row_counts": row_counts, "schema_version": schema_version}



def restore_database(*, db_target: str, backup_path: str, confirm_destructive: bool) -> dict[str, Any]:
    if not confirm_destructive:
        raise BackupRestoreError(
            "Restore is destructive. Re-run with --confirm-destructive to replace current pilot state."
        )
    payload = _load_backup_payload(backup_path)
    _validate_backup_payload(payload)
    store = create_store(db_target)
    store.init_db()
    schema_version = _required_schema_version(store)
    if int(payload["schema_version"]) != int(schema_version):
        raise BackupRestoreError(
            f"Backup schema_version={payload['schema_version']} is incompatible with runtime schema_version={schema_version}."
        )

    restored_counts: dict[str, int] = {}
    with store.connect() as conn:
        for spec in reversed(TABLE_SPECS):
            conn.execute(f"DELETE FROM {spec.name}")
        for spec in TABLE_SPECS:
            rows = payload["tables"].get(spec.name, [])
            if rows:
                placeholders = _placeholders(store, len(spec.columns))
                query = f"INSERT INTO {spec.name}({', '.join(spec.columns)}) VALUES ({placeholders})"
                values = [tuple(row.get(col) for col in spec.columns) for row in rows]
                conn.executemany(query, values)
            restored_counts[spec.name] = len(rows)

    return {"restored_counts": restored_counts, "schema_version": schema_version}



def _load_backup_payload(path: str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BackupRestoreError(f"Backup file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BackupRestoreError(f"Backup file is not valid JSON: {path}") from exc



def _validate_backup_payload(payload: dict[str, Any]) -> None:
    if int(payload.get("backup_format_version", -1)) != BACKUP_FORMAT_VERSION:
        raise BackupRestoreError(
            f"Unsupported backup format version: {payload.get('backup_format_version')} (expected {BACKUP_FORMAT_VERSION})."
        )
    if "schema_version" not in payload:
        raise BackupRestoreError("Backup payload missing schema_version.")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise BackupRestoreError("Backup payload missing tables object.")
    expected_tables = {spec.name for spec in TABLE_SPECS}
    table_keys = set(tables.keys())
    if table_keys != expected_tables:
        raise BackupRestoreError(
            f"Backup table set mismatch. expected={sorted(expected_tables)} got={sorted(table_keys)}"
        )



def _required_schema_version(store: Any) -> int:
    version = getattr(store, "CURRENT_SCHEMA_VERSION", None)
    if version is None:
        raise BackupRestoreError("Store backend does not expose CURRENT_SCHEMA_VERSION.")
    return int(version)



def _placeholders(store: Any, n: int) -> str:
    if store.__class__.__name__ == "PostgresStore":
        return ", ".join("%s" for _ in range(n))
    return ", ".join("?" for _ in range(n))



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
