"""Shared run-scoped data access for diagnostics and exports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.participant_api.persistence.sqlite_store import SQLiteStore, loads
from app.researcher_api.services.run_service import RunService


@dataclass(frozen=True)
class RunScopedData:
    run_id: str
    session_payload: dict[str, Any]
    session_rows: list[dict[str, Any]]
    session_ids: list[str]
    trial_rows: list[dict[str, Any]]
    trial_summary_rows: list[dict[str, Any]]
    event_rows: list[dict[str, Any]]
    questionnaire_rows: list[dict[str, Any]]


class RunDataService:
    """Single source of run/session/trial truth for researcher surfaces."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.run_service = RunService(store)

    def load_run_scoped_data(self, run_id: str) -> RunScopedData:
        session_payload = self.run_service.list_run_sessions(run_id)
        session_rows = list(session_payload["sessions"])
        session_ids = [row["session_id"] for row in session_rows]
        if not session_ids:
            return RunScopedData(
                run_id=run_id,
                session_payload=session_payload,
                session_rows=session_rows,
                session_ids=session_ids,
                trial_rows=[],
                trial_summary_rows=[],
                event_rows=[],
                questionnaire_rows=[],
            )

        placeholders = ",".join("?" for _ in session_ids)
        trial_rows = self.store.fetchall(
            f"""
            SELECT trial_id, session_id, block_id, block_index, trial_index, condition, risk_bucket, policy_decision_json, status, served_at, completed_at
            FROM session_trials
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, block_index, trial_index
            """,
            tuple(session_ids),
        )
        raw_summaries = self.store.fetchall(
            f"""
            SELECT session_id, trial_id, summary_json
            FROM trial_summary_logs
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, trial_id
            """,
            tuple(session_ids),
        )
        event_rows = self.store.fetchall(
            f"""
            SELECT event_id, session_id, block_id, trial_id, timestamp, event_type, payload_json
            FROM trial_event_logs
            WHERE session_id IN ({placeholders})
            ORDER BY timestamp
            """,
            tuple(session_ids),
        )
        questionnaire_rows = self.store.fetchall(
            f"""
            SELECT session_id, block_id, burden, trust, usefulness, submitted_at
            FROM block_questionnaires
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, block_id
            """,
            tuple(session_ids),
        )
        run_by_session = {row["session_id"]: row["run_id"] for row in session_rows}
        trial_by_key = {(row["session_id"], row["trial_id"]): row for row in trial_rows}
        trial_summary_rows: list[dict[str, Any]] = []
        for row in raw_summaries:
            payload = loads(row["summary_json"])
            trial_meta = trial_by_key.get((row["session_id"], row["trial_id"]), {})
            payload.setdefault("run_id", run_by_session.get(row["session_id"], run_id))
            payload.setdefault("session_id", row["session_id"])
            payload.setdefault("trial_id", row["trial_id"])
            payload.setdefault("block_id", trial_meta.get("block_id", ""))
            payload.setdefault("trial_index", trial_meta.get("trial_index"))
            payload.setdefault("block_index", trial_meta.get("block_index"))
            payload.setdefault("risk_bucket", trial_meta.get("risk_bucket", payload.get("risk_bucket", "")))
            trial_summary_rows.append(payload)

        return RunScopedData(
            run_id=run_id,
            session_payload=session_payload,
            session_rows=session_rows,
            session_ids=session_ids,
            trial_rows=trial_rows,
            trial_summary_rows=trial_summary_rows,
            event_rows=event_rows,
            questionnaire_rows=questionnaire_rows,
        )
