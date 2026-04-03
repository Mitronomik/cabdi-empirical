"""Session export service for participant API."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from app.participant_api.persistence.sqlite_store import SQLiteStore, loads


class ExportService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def export_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.fetchone("SELECT * FROM participant_sessions WHERE session_id = ?", (session_id,))
        if session is None:
            raise KeyError("session not found")

        events = self.store.fetchall(
            "SELECT event_id, session_id, block_id, trial_id, timestamp, event_type, payload_json FROM trial_event_logs WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        summaries = self.store.fetchall(
            "SELECT trial_id, summary_json FROM trial_summary_logs WHERE session_id = ? ORDER BY trial_id",
            (session_id,),
        )

        event_lines = []
        for row in events:
            payload = {
                "event_id": row["event_id"],
                "session_id": row["session_id"],
                "block_id": row["block_id"],
                "trial_id": row["trial_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "payload": loads(row["payload_json"]),
            }
            event_lines.append(json.dumps(payload, sort_keys=True))

        csv_buffer = io.StringIO()
        csv_rows = [loads(row["summary_json"]) for row in summaries]
        if csv_rows:
            writer = csv.DictWriter(csv_buffer, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

        questionnaires = self.store.fetchall(
            "SELECT session_id, block_id, burden, trust, usefulness, submitted_at FROM block_questionnaires WHERE session_id = ? ORDER BY block_id",
            (session_id,),
        )

        q_buffer = io.StringIO()
        if questionnaires:
            q_writer = csv.DictWriter(q_buffer, fieldnames=list(questionnaires[0].keys()))
            q_writer.writeheader()
            q_writer.writerows(questionnaires)

        summary_json = {
            "session_id": session["session_id"],
            "participant_id": session["participant_id"],
            "experiment_id": session["experiment_id"],
            "run_id": session["run_id"],
            "status": session["status"],
            "language": session.get("language") or "en",
            "n_events": len(event_lines),
            "n_trial_summaries": len(csv_rows),
        }
        return {
            "session_id": session_id,
            "raw_event_log_jsonl": "\n".join(event_lines),
            "trial_summary_csv": csv_buffer.getvalue(),
            "participant_session_summary": summary_json,
            "block_questionnaire_csv": q_buffer.getvalue(),
        }
