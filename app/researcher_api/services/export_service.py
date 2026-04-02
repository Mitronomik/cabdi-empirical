"""Run-level researcher exports built from existing session artifacts."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.participant_api.persistence.sqlite_store import SQLiteStore, loads
from app.researcher_api.services.run_service import RunService


class AdminExportService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.run_service = RunService(store)

    def export_run(self, run_id: str) -> dict[str, Any]:
        session_payload = self.run_service.list_run_sessions(run_id)
        session_ids = [row["session_id"] for row in session_payload["sessions"]]

        if not session_ids:
            return {
                "run_id": run_id,
                "raw_event_log_jsonl": "",
                "trial_summary_csv": "",
                "session_summary_csv": "",
                "session_summary_json": [],
            }

        placeholders = ",".join("?" for _ in session_ids)
        event_rows = self.store.fetchall(
            f"""
            SELECT event_id, session_id, block_id, trial_id, timestamp, event_type, payload_json
            FROM trial_event_logs
            WHERE session_id IN ({placeholders})
            ORDER BY timestamp
            """,
            tuple(session_ids),
        )
        summary_rows = self.store.fetchall(
            f"SELECT summary_json FROM trial_summary_logs WHERE session_id IN ({placeholders}) ORDER BY session_id, trial_id",
            tuple(session_ids),
        )

        raw_event_log_jsonl = "\n".join(
            json.dumps(
                {
                    "event_id": row["event_id"],
                    "session_id": row["session_id"],
                    "block_id": row["block_id"],
                    "trial_id": row["trial_id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": loads(row["payload_json"]),
                },
                sort_keys=True,
            )
            for row in event_rows
        )

        trial_summaries = [loads(row["summary_json"]) for row in summary_rows]
        trial_summary_csv = _to_csv(trial_summaries)

        session_summary_rows = []
        for row in session_payload["sessions"]:
            session_row = dict(row)
            session_row["run_id"] = run_id
            session_summary_rows.append(session_row)

        return {
            "run_id": run_id,
            "raw_event_log_jsonl": raw_event_log_jsonl,
            "trial_summary_csv": trial_summary_csv,
            "session_summary_csv": _to_csv(session_summary_rows),
            "session_summary_json": session_summary_rows,
        }


def _to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
