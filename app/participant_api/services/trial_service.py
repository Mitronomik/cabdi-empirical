"""Trial serving/submission service for participant API."""

from __future__ import annotations

from datetime import datetime, timezone
import statistics
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
from packages.shared_types.pilot_types import SESSION_STATUS_ABANDONED, StimulusItem, TrialContext


CONFIDENCE_SCALE = {"type": "4_point", "min": 1, "max": 4, "step": 1}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrialService:
    def __init__(self, store: PilotStore, session_service: SessionService) -> None:
        self.store = store
        self.session_service = session_service

    def next_trial(self, session_id: str) -> dict[str, Any] | None:
        session = self.session_service.get_session(session_id)
        progress = self._progress(session_id)
        if session["status"] in {SESSION_STATUS_AWAITING_FINAL_SUBMIT, SESSION_STATUS_FINALIZED}:
            return {"status": session["status"], "session_id": session_id, "no_more_trials": True, "progress": progress}
        if session["status"] in {SESSION_STATUS_PAUSED, SESSION_STATUS_ABANDONED}:
            return {"status": session["status"], "session_id": session_id, "progress": progress}
        if session["status"] not in {SESSION_STATUS_IN_PROGRESS, SESSION_STATUS_CREATED}:
            return {"status": session["status"], "session_id": session_id, "progress": progress}
        self._validate_snapshot_integrity(session)

        blocked = self._questionnaire_block_gate(session_id)
        if blocked:
            self.session_service.mark_questionnaire_stage(session_id, blocked)
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
            base_features = loads(trial["pre_render_features_json"])
            lagged_features = self._lagged_features_from_prior_trials(
                session_id=session_id,
                current_trial_id=trial["trial_id"],
            )
            pre_render_features = {**base_features, **lagged_features}
            context = TrialContext(
                session_id=session_id,
                participant_id=session["participant_id"],
                condition=trial["condition"],
                block_id=trial["block_id"],
                trial_id=trial["trial_id"],
                stimulus=stimulus,
                recent_history={"lagged_window_size": lagged_features["prior_completed_trials_considered"]},
                pre_render_features=pre_render_features,
            )
            risk_bucket, policy_decision = render_policy_decision(context)
            self.store.execute(
                """
                UPDATE session_trials
                SET pre_render_features_json = ?, risk_bucket = ?, policy_decision_json = ?, served_at = ?
                WHERE trial_id = ?
                """,
                (dumps(pre_render_features), risk_bucket, dumps(policy_decision), _now_iso(), trial["trial_id"]),
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
                payload={
                    "assistance_rendered": True,
                    "panel_visible_on_first_paint": None,
                    "shown_help_components": _shown_components(policy_decision),
                    "policy_decision": policy_decision,
                },
            )

        return {
            "block_id": trial["block_id"],
            "trial_id": trial["trial_id"],
            "stimulus": stimulus.to_dict(),
            "policy_decision": policy_decision,
            "self_confidence_scale": CONFIDENCE_SCALE,
            "progress": progress,
            "saved_ack": {"saved": True, "saved_at": session.get("last_activity_at")},
        }

    def _validate_snapshot_integrity(self, session: dict[str, Any]) -> None:
        session_id = str(session["session_id"])
        run = self.store.fetchone("SELECT stimulus_set_ids_json, practice_stimulus_set_id FROM researcher_runs WHERE run_id = ?", (session["run_id"],))
        if run is None:
            raise ValueError("session run reference is invalid")
        main_set_ids = {str(item) for item in loads(run["stimulus_set_ids_json"])}
        practice_set_id = str(run["practice_stimulus_set_id"]) if run.get("practice_stimulus_set_id") else None
        allowed_set_ids = set(main_set_ids)
        if practice_set_id:
            allowed_set_ids.add(practice_set_id)

        total_row = self.store.fetchone("SELECT COUNT(*) AS n FROM session_trials WHERE session_id = ?", (session_id,))
        total_trials = int(total_row["n"]) if total_row else 0
        if total_trials != int(session.get("expected_trial_count", 0)):
            raise ValueError("session trial count mismatch: frozen snapshot is inconsistent")

        stimulus_ids_by_set: dict[str, set[str]] = {}
        for source_set_id in sorted(allowed_set_ids):
            source_row = self.store.fetchone(
                "SELECT items_json FROM researcher_stimulus_sets WHERE stimulus_set_id = ?",
                (source_set_id,),
            )
            if source_row is None:
                raise ValueError("session references missing run stimulus-set source")
            set_item_ids: set[str] = set()
            for raw_item in loads(source_row["items_json"]):
                set_item_ids.add(str(raw_item.get("stimulus_id")))
            stimulus_ids_by_set[source_set_id] = set_item_ids

        trial_rows = self.store.fetchall(
            "SELECT trial_id, block_id, is_practice, stimulus_json, source_stimulus_set_ids_json FROM session_trials WHERE session_id = ?",
            (session_id,),
        )
        for row in trial_rows:
            source_set_ids = set(loads(row.get("source_stimulus_set_ids_json") or "[]"))
            if not source_set_ids:
                raise ValueError("session trial provenance is missing source stimulus-set ids")
            if not source_set_ids.issubset(allowed_set_ids):
                raise ValueError("session contains trials outside run stimulus-set definition")
            stimulus = StimulusItem.from_dict(loads(row["stimulus_json"]))
            if int(row.get("is_practice") or 0) == 1 or str(row.get("block_id")) == "practice":
                if not practice_set_id:
                    raise ValueError("practice trial exists but run has no practice bank")
                if source_set_ids != {practice_set_id}:
                    raise ValueError("practice trial provenance must match configured practice bank")
            else:
                if source_set_ids - main_set_ids:
                    raise ValueError("main trial provenance includes non-main bank source ids")
                if practice_set_id and practice_set_id in source_set_ids:
                    raise ValueError("main trial provenance must not include practice bank source ids")
            if not any(stimulus.stimulus_id in stimulus_ids_by_set[source_id] for source_id in source_set_ids):
                raise ValueError("trial provenance does not match any source item in referenced stimulus set")

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
        if session["status"] == SESSION_STATUS_FINALIZED:
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
            "saved_ack": {"saved": True, "saved_at": session.get("last_activity_at")},
        }

    def submit_block_questionnaire(self, session_id: str, block_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self.session_service.get_session(session_id)
        if session["status"] == SESSION_STATUS_FINALIZED:
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
            "saved_ack": {"saved": True, "saved_at": session.get("last_activity_at")},
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

    def _lagged_features_from_prior_trials(self, session_id: str, current_trial_id: str) -> dict[str, Any]:
        """Derive lagged routing features from prior completed trials in this session.

        Operational semantics:
        - Window: most recent up to 5 *completed* trials before current trial serving.
          Risk-marker counts remain anchored to last 3 to preserve policy contract.
        - error: summary.correct_or_not=False, or fallback from event response_selected
          compared with persisted stimulus true_label when summary is missing.
        - blind acceptance: accepted model advice with wrong model prediction AND no
          observable deliberation (reason/evidence/verification) in prior trace.
          Event trace signals complement/override thin summary booleans.
        - latency bucket: deterministic coarse bucket from prior per-trial observed
          completion latency (trial_completed event payload if present, else summary).
          Sparse or malformed history falls back deterministically.
        """
        rows = self.store.fetchall(
            """
            SELECT st.trial_id, st.stimulus_json, tsl.summary_json
            FROM session_trials st
            LEFT JOIN trial_summary_logs tsl
              ON tsl.session_id = st.session_id AND tsl.trial_id = st.trial_id
            WHERE st.session_id = ?
              AND st.status = 'completed'
              AND st.completed_at IS NOT NULL
              AND st.trial_id != ?
            ORDER BY st.completed_at DESC
            LIMIT 5
            """,
            (session_id, current_trial_id),
        )

        prior_trials: list[dict[str, Any]] = []
        trial_ids: list[str] = []
        for row in rows:
            summary: dict[str, Any] = {}
            stimulus: dict[str, Any] = {}
            if not row["summary_json"]:
                summary = {}
            else:
                try:
                    parsed = loads(row["summary_json"])
                except Exception:
                    parsed = {}
                if isinstance(parsed, dict):
                    summary = parsed
            if row["stimulus_json"]:
                try:
                    stimulus_parsed = loads(row["stimulus_json"])
                except Exception:
                    stimulus_parsed = {}
                if isinstance(stimulus_parsed, dict):
                    stimulus = stimulus_parsed

            trial_id = str(row["trial_id"])
            trial_ids.append(trial_id)
            prior_trials.append({"trial_id": trial_id, "summary": summary, "stimulus": stimulus})

        trial_events = _load_trial_events(store=self.store, session_id=session_id, trial_ids=trial_ids)

        lagged_records = [
            _build_prior_trial_behavior_record(trial=trial, events=trial_events.get(trial["trial_id"], []))
            for trial in prior_trials
        ]

        marker_window = lagged_records[:3]
        recent_error_count = sum(1 for record in marker_window if record["is_error"])
        recent_blind_accept_count = sum(1 for record in marker_window if record["is_blind_accept"])
        latency_bucket = _latency_bucket_from_prior_records(lagged_records)

        return {
            "recent_error_count_last_3": recent_error_count,
            "recent_blind_accept_count_last_3": recent_blind_accept_count,
            "recent_latency_z_bucket": latency_bucket,
            "prior_completed_trials_considered": len(lagged_records),
        }

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


def _load_trial_events(store: PilotStore, session_id: str, trial_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not trial_ids:
        return {}
    placeholders = ", ".join("?" for _ in trial_ids)
    rows = store.fetchall(
        f"""
        SELECT trial_id, event_type, payload_json, timestamp
        FROM trial_event_logs
        WHERE session_id = ?
          AND trial_id IN ({placeholders})
        ORDER BY timestamp
        """,
        (session_id, *trial_ids),
    )
    grouped: dict[str, list[dict[str, Any]]] = {trial_id: [] for trial_id in trial_ids}
    for row in rows:
        payload: dict[str, Any] = {}
        if row["payload_json"]:
            try:
                parsed = loads(row["payload_json"])
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                payload = parsed
        grouped.setdefault(str(row["trial_id"]), []).append(
            {"event_type": row["event_type"], "payload": payload, "timestamp": row["timestamp"]}
        )
    return grouped


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _build_prior_trial_behavior_record(trial: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    summary = trial["summary"]
    stimulus = trial["stimulus"]

    response_from_event: str | None = None
    rt_from_event: int | None = None
    observed_deliberation = False
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload", {})
        if event_type == "response_selected":
            maybe_response = payload.get("human_response")
            if isinstance(maybe_response, str):
                response_from_event = maybe_response
        elif event_type == "trial_completed":
            rt_from_event = _parse_int(payload.get("reaction_time_ms"))
        elif event_type in {"reason_clicked", "evidence_opened", "verification_checked"}:
            observed_value = payload.get("value", True)
            if observed_value is not False:
                observed_deliberation = True

    accepted_model = _parse_bool(summary.get("accepted_model_advice"))
    if accepted_model is None:
        model_prediction = stimulus.get("model_prediction")
        if isinstance(model_prediction, str) and response_from_event is not None:
            accepted_model = response_from_event == model_prediction

    model_wrong = _parse_bool(summary.get("model_correct_or_not"))
    if model_wrong is None:
        model_wrong = _parse_bool(stimulus.get("model_correct"))
    model_is_wrong = (model_wrong is False) if model_wrong is not None else False

    summary_deliberation = any(
        _parse_bool(summary.get(field)) is True for field in ("reason_clicked", "evidence_opened", "verification_completed")
    )

    is_blind_accept = bool(accepted_model is True and model_is_wrong and not (summary_deliberation or observed_deliberation))

    is_error = _parse_bool(summary.get("correct_or_not"))
    if is_error is None:
        true_label = stimulus.get("true_label")
        if isinstance(true_label, str) and response_from_event is not None:
            is_error = response_from_event == true_label
    is_error_final = (is_error is False) if is_error is not None else False

    latency_ms = rt_from_event
    if latency_ms is None:
        latency_ms = _parse_int(summary.get("reaction_time_ms"))

    return {
        "is_error": is_error_final,
        "is_blind_accept": is_blind_accept,
        "latency_ms": latency_ms,
    }


def _latency_bucket_from_prior_records(records: list[dict[str, Any]]) -> str:
    latencies = [record["latency_ms"] for record in records if isinstance(record.get("latency_ms"), int)]
    if not latencies:
        return "medium"
    if len(latencies) == 1:
        if latencies[0] >= 1800:
            return "high"
        if latencies[0] <= 800:
            return "low"
        return "medium"

    median_latency = statistics.median(latencies)
    latest_latency = latencies[0]
    if median_latency >= 1600 or latest_latency >= 2200:
        return "high"
    if median_latency <= 900 and latest_latency <= 1200:
        return "low"
    return "medium"


def _latency_bucket_from_summaries(summaries: list[dict[str, Any]]) -> str:
    """Backward-compatible helper used by tests for sparse fallback semantics."""
    records = [{"latency_ms": _parse_int(summary.get("reaction_time_ms"))} for summary in summaries]
    return _latency_bucket_from_prior_records(records)
