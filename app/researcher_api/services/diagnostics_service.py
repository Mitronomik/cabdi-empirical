"""Run-level lightweight diagnostics for researcher admin."""

from __future__ import annotations

from collections import Counter, defaultdict
import os
from typing import Any

from app.participant_api.persistence.json_codec import loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.researcher_api.services.run_data_service import RunDataService
from app.researcher_api.services.run_service import (
    _resolve_stale_session_threshold_minutes,
    build_session_operational_summary,
)
from packages.shared_types.pilot_types import RiskBucket
from policies.budget_checks import compare_budget_to_reference, summarize_budgets_by_condition
from policies.contracts import BudgetTrace
from policies.pilot_rules import expected_budget_signature

_CORE_SUMMARY_FIELDS = [
    "participant_id",
    "session_id",
    "experiment_id",
    "condition",
    "stimulus_id",
    "true_label",
    "human_response",
    "model_prediction",
    "risk_bucket",
    "reaction_time_ms",
]


class DiagnosticsService:
    def __init__(self, store: PilotStore) -> None:
        self.store = store
        self.run_data_service = RunDataService(store)
        self.stale_session_threshold_minutes = _resolve_stale_session_threshold_minutes(
            os.getenv("PILOT_STALE_SESSION_THRESHOLD_MINUTES")
        )

    def get_run_diagnostics(self, run_id: str) -> dict[str, Any]:
        run_data = self.run_data_service.load_run_scoped_data(run_id)
        session_info = run_data.session_payload
        session_ids = run_data.session_ids

        if not session_ids:
            empty_operational_summary = build_session_operational_summary(
                [],
                stale_session_threshold_minutes=self.stale_session_threshold_minutes,
            )
            return {
                "run_id": run_id,
                "session_counts": session_info["counts"],
                "session_count_total": 0,
                "trial_count_total": 0,
                "trial_summary_count": 0,
                "missing_core_fields_count": 0,
                "completed_trials_per_condition": {},
                "model_wrong_share": {},
                "verification_usage_rate": 0.0,
                "reason_click_rate": 0.0,
                "evidence_open_rate": 0.0,
                "block_order_distribution": {},
                "budget_tolerance_flags": [],
                "stale_session_count": int(empty_operational_summary["stale_session_count"]),
                "operational_summary": empty_operational_summary,
                "warnings": ["No sessions linked to this run yet"],
                "run_level_flags": [
                    {
                        "severity": "warning",
                        "code": "no_sessions",
                        "message": "Run has no linked sessions; confirmatory and narrowing interpretations are not available.",
                    }
                ],
                "cohort_level_flags": [
                    {
                        "severity": "warning",
                        "code": "insufficient_sample",
                        "message": "No cohort observations are available yet.",
                    }
                ],
            }

        parsed_summaries = list(run_data.trial_summary_rows)
        trial_lookup = {(row["session_id"], row["trial_id"]): row for row in run_data.trial_rows}
        missing_core_fields_count = 0
        completed_trials_per_condition: dict[str, int] = Counter()
        model_wrong_counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
        verification_count = 0
        reason_count = 0
        evidence_count = 0

        for summary in parsed_summaries:
            for field in _CORE_SUMMARY_FIELDS:
                value = summary.get(field)
                if value is None or value == "":
                    missing_core_fields_count += 1
            condition = str(summary.get("condition", "unknown"))
            trial_meta = trial_lookup.get((str(summary.get("session_id", "")), str(summary.get("trial_id", ""))), {})
            block_id = str(trial_meta.get("block_id", "unknown"))
            completed_trials_per_condition[condition] += 1
            model_wrong_counts[(condition, block_id)][1] += 1
            if not bool(summary.get("model_correct_or_not", True)):
                model_wrong_counts[(condition, block_id)][0] += 1

            verification_count += int(bool(summary.get("verification_completed", False)))
            reason_count += int(bool(summary.get("reason_clicked", False)))
            evidence_count += int(bool(summary.get("evidence_opened", False)))

        block_order_distribution: dict[str, int] = Counter()
        for session_id in session_ids:
            rows = self.store.fetchall(
                "SELECT DISTINCT block_id FROM session_trials WHERE session_id = ? AND block_id != 'practice' ORDER BY block_index",
                (session_id,),
            )
            order_key = "->".join(row["block_id"] for row in rows)
            block_order_distribution[order_key] += 1

        model_wrong_share = {
            f"{condition}|{block_id}": (wrong / total if total else 0.0)
            for (condition, block_id), (wrong, total) in model_wrong_counts.items()
        }

        budget_observed, budget_reference, budget_flags = self._budget_diagnostics(
            run_data.trial_rows,
            run_data.trial_summary_rows,
        )
        n_trials = max(len(parsed_summaries), 1)
        warnings = []
        if len(parsed_summaries) != len(
            [row for row in run_data.trial_rows if row["status"] == "completed" and row["block_id"] != "practice"]
        ):
            warnings.append(
                "Trial-summary count differs from completed non-practice trials; check for partial or missing summary logs"
            )
        if missing_core_fields_count > 0:
            warnings.append(f"Missing core log fields detected: {missing_core_fields_count}")
        if len(parsed_summaries) == 0 and len(run_data.trial_rows) > 0:
            warnings.append("No trial summaries logged for this run yet")
        if any(flag["kind"] in {"missing_reference", "insufficient_budget_data"} for flag in budget_flags):
            warnings.append("Budget diagnostics are incomplete; matched-budget interpretation is unresolved for this run")
        operational_summary = build_session_operational_summary(
            session_info.get("sessions", []),
            stale_session_threshold_minutes=self.stale_session_threshold_minutes,
        )
        stale_session_count = int(operational_summary["stale_session_count"])
        if stale_session_count > 0:
            warnings.insert(0, f"Potential stale sessions: {stale_session_count}")
        if int(operational_summary["lifecycle_anomaly_count"]) > 0:
            warnings.append(f"Lifecycle anomalies detected: {int(operational_summary['lifecycle_anomaly_count'])}")
        run_level_flags, cohort_level_flags = self._analysis_flags(
            trial_summary_count=len(parsed_summaries),
            missing_core_fields_count=missing_core_fields_count,
            warnings=warnings,
            budget_flags=budget_flags,
            stale_session_count=stale_session_count,
            session_count_total=len(session_ids),
            completed_trials_per_condition=dict(completed_trials_per_condition),
        )

        return {
            "run_id": run_id,
            "session_counts": session_info["counts"],
            "session_count_total": len(session_ids),
            "trial_count_total": len(run_data.trial_rows),
            "trial_summary_count": len(parsed_summaries),
            "missing_core_fields_count": missing_core_fields_count,
            "completed_trials_per_condition": dict(completed_trials_per_condition),
            "model_wrong_share": model_wrong_share,
            "verification_usage_rate": verification_count / n_trials,
            "reason_click_rate": reason_count / n_trials,
            "evidence_open_rate": evidence_count / n_trials,
            "block_order_distribution": dict(block_order_distribution),
            "budget_observed_by_condition": budget_observed,
            "budget_reference_by_condition": budget_reference,
            "budget_tolerance_flags": budget_flags,
            "stale_session_count": stale_session_count,
            "operational_summary": operational_summary,
            "warnings": warnings,
            "run_level_flags": run_level_flags,
            "cohort_level_flags": cohort_level_flags,
        }

    def _analysis_flags(
        self,
        *,
        trial_summary_count: int,
        missing_core_fields_count: int,
        warnings: list[str],
        budget_flags: list[dict[str, Any]],
        stale_session_count: int,
        session_count_total: int,
        completed_trials_per_condition: dict[str, int],
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        run_level_flags: list[dict[str, str]] = []
        cohort_level_flags: list[dict[str, str]] = []

        if trial_summary_count == 0:
            run_level_flags.append(
                {
                    "severity": "warning",
                    "code": "no_trial_summaries",
                    "message": "No trial summaries logged; analysis-ready confirmatory interpretation is unavailable.",
                }
            )
        if missing_core_fields_count > 0:
            run_level_flags.append(
                {
                    "severity": "warning",
                    "code": "missing_core_fields",
                    "message": "Core trial-summary fields are missing; claim-facing interpretation should be treated as narrowing-only.",
                }
            )
        if any(flag.get("kind") in {"missing_reference", "insufficient_budget_data"} for flag in budget_flags):
            run_level_flags.append(
                {
                    "severity": "warning",
                    "code": "budget_diagnostics_incomplete",
                    "message": "Matched-budget diagnostics are incomplete; admissible confirmatory comparisons are unresolved.",
                }
            )
        if stale_session_count > 0:
            run_level_flags.append(
                {
                    "severity": "warning",
                    "code": "stale_sessions_detected",
                    "message": "Stale sessions detected; lifecycle truth requires operator review before confirmatory claims.",
                }
            )
        if any("Lifecycle anomalies detected" in warning for warning in warnings):
            run_level_flags.append(
                {
                    "severity": "warning",
                    "code": "lifecycle_anomaly",
                    "message": "Lifecycle anomalies detected in run-bound sessions.",
                }
            )
        if not run_level_flags:
            run_level_flags.append(
                {
                    "severity": "info",
                    "code": "run_ready_for_behavior_first_analysis",
                    "message": "Run diagnostics pass minimum behavior-first analysis readiness checks.",
                }
            )

        min_condition_trials = min(completed_trials_per_condition.values()) if completed_trials_per_condition else 0
        if session_count_total < 4 or min_condition_trials < 5:
            cohort_level_flags.append(
                {
                    "severity": "warning",
                    "code": "insufficient_sample",
                    "message": "Cohort sample is small for confirmatory mixed-effects use; treat outputs as narrowing or exploratory.",
                }
            )
        else:
            cohort_level_flags.append(
                {
                    "severity": "info",
                    "code": "cohort_minimum_met",
                    "message": "Minimum cohort coverage met for behavior-first confirmatory modeling attempts.",
                }
            )
        return run_level_flags, cohort_level_flags

    def _budget_diagnostics(
        self,
        trial_rows: list[dict[str, Any]],
        trial_summary_rows: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], list[dict[str, Any]]]:
        traces: list[BudgetTrace] = []
        reference_traces: list[BudgetTrace] = []
        flags: list[dict[str, Any]] = []
        summary_by_trial = {
            (str(row.get("session_id", "")), str(row.get("trial_id", ""))): row for row in trial_summary_rows
        }
        for row in trial_rows:
            if row.get("block_id") == "practice" or row.get("status") != "completed":
                continue
            decision_payload = row.get("policy_decision_json")
            if not decision_payload:
                flags.append(
                    {
                        "condition": row.get("condition", "unknown"),
                        "severity": "warning",
                        "kind": "insufficient_budget_data",
                        "message": "Missing policy_decision_json for completed trial",
                        "session_id": row.get("session_id"),
                        "trial_id": row.get("trial_id"),
                    }
                )
                continue
            decision = loads(decision_payload)
            summary = summary_by_trial.get((row["session_id"], row["trial_id"]), {})
            realized_extra_steps = int(bool(summary.get("reason_clicked"))) + int(bool(summary.get("evidence_opened")))
            verification_actions = int(bool(summary.get("verification_completed")))
            traces.append(
                BudgetTrace(
                    condition=row["condition"],
                    risk_bucket=RiskBucket(decision["risk_bucket"]),
                    shown_components_count=int(decision["budget_signature"].get("shown_components_count", 0)),
                    shown_text_tokens=int(decision["budget_signature"].get("text_tokens_shown", 0)),
                    display_load_units=int(
                        decision["budget_signature"].get(
                            "display_load_units",
                            decision["budget_signature"].get("shown_components_count", 0),
                        )
                    ),
                    interaction_load_units=int(
                        decision["budget_signature"].get(
                            "interaction_load_units",
                            decision["budget_signature"].get("max_extra_steps", 0),
                        )
                    ),
                    provenance_cue_units=int(
                        decision["budget_signature"].get(
                            "provenance_cue_units",
                            int(decision["budget_signature"].get("evidence_available_count", 0))
                            + int(decision["budget_signature"].get("shown_components_count", 0) > 1),
                        )
                    ),
                    evidence_available=int(decision["budget_signature"].get("evidence_available_count", 0)),
                    max_extra_steps=int(decision["budget_signature"].get("max_extra_steps", 0)),
                    realized_extra_steps=realized_extra_steps + verification_actions,
                    verification_actions=verification_actions,
                    block_id=row["block_id"],
                )
            )
            try:
                risk_bucket = RiskBucket(str(row.get("risk_bucket") or decision["risk_bucket"]))
                ref_signature = expected_budget_signature(row["condition"], risk_bucket)
                reference_traces.append(
                    BudgetTrace(
                        condition=row["condition"],
                        risk_bucket=risk_bucket,
                        shown_components_count=int(ref_signature["shown_components_count"]),
                        shown_text_tokens=int(ref_signature["text_tokens_shown"]),
                        display_load_units=int(ref_signature.get("display_load_units", ref_signature["shown_components_count"])),
                        interaction_load_units=int(ref_signature.get("interaction_load_units", ref_signature["max_extra_steps"])),
                        provenance_cue_units=int(
                            ref_signature.get(
                                "provenance_cue_units",
                                int(ref_signature["evidence_available_count"]) + int(ref_signature["shown_components_count"] > 1),
                            )
                        ),
                        evidence_available=int(ref_signature["evidence_available_count"]),
                        max_extra_steps=int(ref_signature["max_extra_steps"]),
                        realized_extra_steps=int(ref_signature["max_extra_steps"]),
                        verification_actions=0,
                        block_id=row["block_id"],
                    )
                )
            except (KeyError, ValueError):
                flags.append(
                    {
                        "condition": row.get("condition", "unknown"),
                        "severity": "warning",
                        "kind": "missing_reference",
                        "message": "No condition/risk reference available for trial",
                        "session_id": row.get("session_id"),
                        "trial_id": row.get("trial_id"),
                    }
                )

        if not traces:
            return {}, {}, flags

        observed = summarize_budgets_by_condition(traces)
        reference = summarize_budgets_by_condition(reference_traces) if reference_traces else {}
        flags.extend(
            compare_budget_to_reference(
                observed=observed,
                reference=reference,
                text_budget_tolerance_pct=20.0,
                interaction_budget_tolerance_pct=20.0,
                hard_max_extra_steps_per_trial=1,
            )
        )
        return observed, reference, flags
