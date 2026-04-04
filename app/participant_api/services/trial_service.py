"""Trial serving/submission service for participant API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.json_codec import dumps, loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.participant_api.services.policy_service import render_policy_decision
from app.participant_api.services.session_service import (
    SESSION_STATUS_AWAITING_FINAL_SUBMIT,
    SESSION_STATUS_FINALIZED,
    SESSION_STATUS_CREATED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_PAUSED,
    SessionService,
)
from packages.logging_schema.pilot_logs import TrialEventLog, TrialSummaryLog
from packages.shared_types.pilot_types import StimulusItem, TrialContext


CONFIDENCE_SCALE = {"min": 0, "max": 100, "step": 1}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrialService:
    def __init__(self, store: PilotStore, session_service: SessionService) -> None:
        self.store = store
        self.session_service = session_service

    def next_trial(self, session_id: str) -> dict[str, Any] | None:
        session = self.session_service.get_session(session_id)
        progress = self._progress(session_id)
        if session["status"] in {SESSION_STATUS_AWAITING_FINAL_SUBMIT, SESSION_STATUS_FINALIZED, "completed"}:
            return {"status": session["status"], "session_id": session_id, "no_more_trials": True, "progress": progress}
        if session["status"] in {SESSION_STATUS_PAUSED, "abandoned"}:
            return {"status": session["status"], "session_id": session_id, "progress": progress}
        if session["status"] not in {SESSION_STATUS_IN_PROGRESS, SESSION_STATUS_CREATED}:
            return {"status": session["status"], "session_id": session_id, "progress": progress}

        blocked = self._questionnaire_block_gate(session_id)
        if blocked:
            raise ValueError(f"block_questionnaire_required:{blocked}")

        trial = self.store.fetchone(
            """
            SELECT * FROM session_trials
            WHERE session_id = ? AND status = 'pending'
            ORDER BY CASE WHEN block_index = -1 THEN -1 ELSE block_index END, trial_index
            LIMIT 1
            """,
            (session_id,),
        )
        if trial is None:
            moved = self.session_service.mark_awaiting_final_submit_if_done(session_id)
            status = SESSION_STATUS_AWAITING_FINAL_SUBMIT if moved else self.session_service.get_session(session_id)["status"]
            return {"status": status, "session_id": session_id, "no_more_trials": True, "progress": self._progress(session_id)}

        stimulus = StimulusItem.from_dict(loads(trial["stimulus_json"]))
        if trial["policy_decision_json"]:
            policy_decision = loads(trial["policy_decision_json"])
            risk_bucket = trial["risk_bucket"]
        else:
            context = TrialContext(
                session_id=session_id,
                participant_id=session["participant_id"],
                condition=trial["condition"],
                block_id=trial["block_id"],
                trial_id=trial["trial_id"],
                stimulus=stimulus,
                recent_history={},
                pre_render_features=loads(trial["pre_render_features_json"]),
            )
            risk_bucket, policy_decision = render_policy_decision(context)
            self.store.execute(
                "UPDATE session_trials SET risk_bucket = ?, policy_decision_json = ?, served_at = ? WHERE trial_id = ?",
                (risk_bucket, dumps(policy_decision), _now_iso(), trial["trial_id"]),
            )
            self._log_event(
                session_id=session_id,
                block_id=trial["block_id"],
                trial_id=trial["trial_id"],
                event_type="trial_started",
                payload={"condition": trial["condition"]},
            )
            self._log_event(
                session_id=session_id,
                block_id=trial["block_id"],
                trial_id=trial["trial_id"],
                event_type="assistance_rendered",
                payload={"policy_decision": policy_decision},
            )

        return {
            "block_id": trial["block_id"],
            "trial_id": trial["trial_id"],
            "stimulus": stimulus.to_dict(),
            "policy_decision": policy_decision,
            "self_confidence_scale": CONFIDENCE_SCALE,
            "progress": progress,
        }

    def _progress(self, session_id: str) -> dict[str, int]:
        total_row = self.store.fetchone("SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?", (session_id,))
        completed_row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ? AND status = 'completed'",
            (session_id,),
        )
        total = int(total_row["n"]) if total_row else 0
        completed = int(completed_row["n"]) if completed_row else 0
        return {
            "total_trials": total,
            "completed_trials": completed,
            "current_ordinal": min(completed + 1, total) if total > 0 else 0,
        }

    def submit_trial(self, session_id: str, trial_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self.session_service.get_session(session_id)
        if session["status"] in {SESSION_STATUS_FINALIZED, "completed"}:
            raise ValueError("session_finalized")
        trial = self.store.fetchone(
            "SELECT * FROM session_trials WHERE session_id = ? AND trial_id = ?",
            (session_id, trial_id),
        )
        if trial is None:
            raise KeyError("trial not found")
        if trial["status"] == "completed":
            return {"trial_id": trial_id, "status": "completed"}

        stimulus = StimulusItem.from_dict(loads(trial["stimulus_json"]))
        policy_decision = loads(trial["policy_decision_json"])
        if payload.get("event_trace"):
            for event in payload["event_trace"]:
                self._log_event(
                    session_id=session_id,
                    block_id=trial["block_id"],
                    trial_id=trial_id,
                    event_type=event["event_type"],
                    payload=event.get("payload", {}),
                )

        if payload.get("reason_clicked"):
            self._log_event(session_id, trial["block_id"], trial_id, "reason_clicked", {"value": True})
        if payload.get("evidence_opened"):
            self._log_event(session_id, trial["block_id"], trial_id, "evidence_opened", {"value": True})
        if payload.get("verification_completed"):
            self._log_event(session_id, trial["block_id"], trial_id, "verification_checked", {"value": True})

        self._log_event(session_id, trial["block_id"], trial_id, "response_selected", {"human_response": payload["human_response"]})
        self._log_event(session_id, trial["block_id"], trial_id, "confidence_submitted", {"self_confidence": payload["self_confidence"]})
        self._log_event(session_id, trial["block_id"], trial_id, "trial_completed", {"reaction_time_ms": payload["reaction_time_ms"]})

        summary = TrialSummaryLog(
            participant_id=self.session_service.get_session(session_id)["participant_id"],
            session_id=session_id,
            experiment_id=self.session_service.get_session(session_id)["experiment_id"],
            condition=trial["condition"],
            stimulus_id=stimulus.stimulus_id,
            task_family=stimulus.task_family,
            true_label=stimulus.true_label,
            human_response=payload["human_response"],
            correct_or_not=payload["human_response"] == stimulus.true_label,
            model_prediction=stimulus.model_prediction,
            model_confidence=stimulus.model_confidence,
            model_correct_or_not=stimulus.model_correct,
            risk_bucket=trial["risk_bucket"],
            shown_help_level=policy_decision["ui_help_level"],
            shown_verification_level=policy_decision["ui_verification_level"],
            shown_components=_shown_components(policy_decision),
            accepted_model_advice=payload["human_response"] == stimulus.model_prediction,
            overrode_model=payload["human_response"] != stimulus.model_prediction,
            verification_required=policy_decision["verification_mode"] != "none",
            verification_completed=bool(payload["verification_completed"]),
            reason_clicked=bool(payload["reason_clicked"]),
            evidence_opened=bool(payload["evidence_opened"]),
            reaction_time_ms=int(payload["reaction_time_ms"]),
            self_confidence=int(payload["self_confidence"]),
        )
        self.store.execute(
            """
            INSERT INTO trial_summary_logs(session_id, trial_id, summary_json)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id, trial_id) DO UPDATE SET summary_json = excluded.summary_json
            """,
            (session_id, trial_id, dumps(summary.to_dict())),
        )

        self.store.execute(
            "UPDATE session_trials SET status = 'completed', completed_at = ? WHERE trial_id = ?",
            (_now_iso(), trial_id),
        )
        self.session_service.update_progress(session_id)
        awaiting_final_submit = self.session_service.mark_awaiting_final_submit_if_done(session_id)
        session = self.session_service.get_session(session_id)
        return {
            "trial_id": trial_id,
            "status": "completed",
            "session_completed": awaiting_final_submit,
            "session_status": session["status"],
        }

    def submit_block_questionnaire(self, session_id: str, block_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self.session_service.get_session(session_id)
        if session["status"] in {SESSION_STATUS_FINALIZED, "completed"}:
            raise ValueError("session_finalized")
        self.store.execute(
            """
            INSERT INTO block_questionnaires(session_id, block_id, burden, trust, usefulness, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, block_id) DO UPDATE SET
                burden = excluded.burden,
                trust = excluded.trust,
                usefulness = excluded.usefulness,
                submitted_at = excluded.submitted_at
            """,
            (
                session_id,
                block_id,
                payload.get("burden"),
                payload.get("trust"),
                payload.get("usefulness"),
                _now_iso(),
            ),
        )
        self.session_service.update_progress(session_id)
        awaiting_final_submit = self.session_service.mark_awaiting_final_submit_if_done(session_id)
        session = self.session_service.get_session(session_id)
        return {
            "block_id": block_id,
            "status": "submitted",
            "session_completed": awaiting_final_submit,
            "session_status": session["status"],
        }

    def _questionnaire_block_gate(self, session_id: str) -> str | None:
        rows = self.store.fetchall(
            """
            SELECT
                block_id,
                COUNT(*) AS n_trials,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS n_done
            FROM session_trials
            WHERE session_id = ? AND block_id != 'practice'
            GROUP BY block_id
            ORDER BY block_id
            """,
            (session_id,),
        )

        for row in rows:
            if row["n_trials"] == row["n_done"]:
                q = self.store.fetchone(
                    """
                    SELECT questionnaire_id
                    FROM block_questionnaires
                    WHERE session_id = ? AND block_id = ?
                    """,
                    (session_id, row["block_id"]),
                )
                if q is None:
                    return str(row["block_id"])

        return None

    def _log_event(self, session_id: str, block_id: str, trial_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = TrialEventLog(
            event_id=f"evt_{uuid4().hex[:14]}",
            session_id=session_id,
            block_id=block_id,
            trial_id=trial_id,
            timestamp=_now_iso(),
            event_type=event_type,
            payload=payload,
        )
        self.store.execute(
            "INSERT INTO trial_event_logs(event_id, session_id, block_id, trial_id, timestamp, event_type, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.block_id,
                event.trial_id,
                event.timestamp,
                event.event_type,
                dumps(event.payload),
            ),
        )


def _shown_components(policy_decision: dict[str, Any]) -> list[str]:
    components = ["prediction"] if policy_decision["show_prediction"] else []
    if policy_decision["show_confidence"]:
        components.append("confidence")
    if policy_decision["show_rationale"] != "none":
        components.append("rationale")
    if policy_decision["show_evidence"]:
        components.append("evidence")
    return components
