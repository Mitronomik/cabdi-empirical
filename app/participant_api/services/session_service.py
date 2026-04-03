"""Session lifecycle service for pilot participant API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.sqlite_store import SQLiteStore, dumps, loads
from app.participant_api.services.randomization_service import assign_order_id, build_trial_plan
from packages.shared_types.pilot_types import ParticipantSession, StimulusItem
from pilot.config_loader import load_experiment_config
from pilot.stimulus_validation import load_stimulus_bank

DEFAULT_EXPERIMENT_PATH = "pilot/configs/default_experiment.yaml"
DEFAULT_STIMULI_PATH = "pilot/stimuli/scam_not_scam_demo.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    @staticmethod
    def _normalize_language(language: str | None) -> str:
        if language in {"en", "ru"}:
            return language
        return "en"

    def create_session(
        self,
        experiment_id: str,
        participant_id: str,
        run_id: str,
        language: str | None = None,
    ) -> dict[str, Any]:
        experiment = load_experiment_config(DEFAULT_EXPERIMENT_PATH)
        if experiment_id != "toy_v1" and experiment_id != experiment.experiment_id:
            raise ValueError(f"Unsupported experiment_id: {experiment_id}")
        if not run_id.strip():
            raise ValueError("run_id is required")

        run = self.store.fetchone("SELECT run_id, experiment_id FROM researcher_runs WHERE run_id = ?", (run_id,))
        if run is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        if run["experiment_id"] != experiment_id:
            raise ValueError("run_id and experiment_id mismatch")

        stimuli = load_stimulus_bank(DEFAULT_STIMULI_PATH)
        order_id, assigned_order = assign_order_id(participant_id, experiment.experiment_id)
        session_id = f"sess_{uuid4().hex[:12]}"
        normalized_language = self._normalize_language(language)

        session = ParticipantSession(
            session_id=session_id,
            participant_id=participant_id,
            experiment_id=experiment_id,
            run_id=run_id,
            assigned_order=order_id,
            stimulus_set_map={"default": "demo"},
            current_block_index=-1,
            current_trial_index=0,
            status="created",
            started_at=_now_iso(),
            completed_at=None,
            device_info={},
            language=normalized_language,
        )

        self.store.execute(
            """
            INSERT INTO participant_sessions(
                session_id, participant_id, experiment_id, run_id, assigned_order, stimulus_set_map,
                current_block_index, current_trial_index, status, started_at, completed_at, device_info, language
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.session_id,
                session.participant_id,
                session.experiment_id,
                session.run_id,
                session.assigned_order,
                dumps(session.stimulus_set_map),
                session.current_block_index,
                session.current_trial_index,
                session.status,
                session.started_at,
                session.completed_at,
                dumps(session.device_info),
                session.language,
            ),
        )

        trial_plan = build_trial_plan(participant_id, experiment, assigned_order, [StimulusItem.from_dict(s.to_dict()) for s in stimuli])
        trial_rows = []
        for idx, trial in enumerate(trial_plan):
            trial_id = f"{session_id}_t{idx+1:03d}"
            trial_rows.append(
                (
                    trial_id,
                    session_id,
                    trial["block_id"],
                    int(trial["block_index"]),
                    int(trial["trial_index"]),
                    trial["condition"],
                    dumps(trial["stimulus"]),
                    dumps(trial["pre_render_features"]),
                    None,
                    None,
                    None,
                    None,
                    "pending",
                )
            )
        self.store.executemany(
            """
            INSERT INTO session_trials(
                trial_id, session_id, block_id, block_index, trial_index, condition,
                stimulus_json, pre_render_features_json, risk_bucket, policy_decision_json,
                served_at, completed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trial_rows,
        )

        return {"session_id": session_id, "status": "created", "assigned_order": order_id, "run_id": session.run_id, "language": session.language}

    def start_session(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session["status"] == "completed":
            return {"session_id": session_id, "status": "completed"}
        self.store.execute(
            "UPDATE participant_sessions SET status = ?, started_at = ? WHERE session_id = ?",
            ("in_progress", _now_iso(), session_id),
        )
        return {"session_id": session_id, "status": "in_progress"}

    def get_session(self, session_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM participant_sessions WHERE session_id = ?", (session_id,))
        if row is None:
            raise KeyError("session not found")
        row["stimulus_set_map"] = loads(row["stimulus_set_map"])
        row["device_info"] = loads(row["device_info"])
        row["language"] = row.get("language") or "en"
        return row

    def update_progress(self, session_id: str) -> None:
        completed = self.store.fetchall(
            "SELECT block_index, trial_index, block_id FROM session_trials WHERE session_id = ? AND status = 'completed' ORDER BY block_index, trial_index",
            (session_id,),
        )
        if not completed:
            self.store.execute(
                "UPDATE participant_sessions SET current_block_index = ?, current_trial_index = ? WHERE session_id = ?",
                (-1, 0, session_id),
            )
            return

        last = completed[-1]
        current_block_index = int(last["block_index"])
        current_trial_index = int(last["trial_index"]) + 1
        self.store.execute(
            "UPDATE participant_sessions SET current_block_index = ?, current_trial_index = ? WHERE session_id = ?",
            (current_block_index, current_trial_index, session_id),
        )

    def mark_completed_if_done(self, session_id: str) -> bool:
        pending = self.store.fetchone(
            "SELECT trial_id FROM session_trials WHERE session_id = ? AND status != 'completed' LIMIT 1",
            (session_id,),
        )
        if pending:
            return False

        main_blocks = self.store.fetchall(
            "SELECT DISTINCT block_id FROM session_trials WHERE session_id = ? AND block_id != 'practice'",
            (session_id,),
        )
        for block in main_blocks:
            q = self.store.fetchone(
                "SELECT questionnaire_id FROM block_questionnaires WHERE session_id = ? AND block_id = ?",
                (session_id, block["block_id"]),
            )
            if q is None:
                return False

        self.store.execute(
            "UPDATE participant_sessions SET status = ?, completed_at = ? WHERE session_id = ?",
            ("completed", _now_iso(), session_id),
        )
        return True
