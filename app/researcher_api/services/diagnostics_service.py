"""Run-level lightweight diagnostics for researcher admin."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.participant_api.persistence.sqlite_store import SQLiteStore, loads
from app.researcher_api.services.run_data_service import RunDataService
from packages.shared_types.pilot_types import RiskBucket
from policies.budget_checks import compare_budget_to_reference, summarize_budgets_by_condition
from policies.contracts import BudgetTrace

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
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.run_data_service = RunDataService(store)

    def get_run_diagnostics(self, run_id: str) -> dict[str, Any]:
        run_data = self.run_data_service.load_run_scoped_data(run_id)
        session_info = run_data.session_payload
        session_ids = run_data.session_ids

        if not session_ids:
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
                "warnings": ["No sessions linked to this run yet"],
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

        budget_flags = self._budget_flags(run_data.trial_rows)
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
            "budget_tolerance_flags": budget_flags,
            "warnings": warnings,
        }

    def _budget_flags(self, trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        traces: list[BudgetTrace] = []
        for row in trial_rows:
            decision_payload = row.get("policy_decision_json")
            if not decision_payload:
                continue
            decision = loads(decision_payload)
            traces.append(
                BudgetTrace(
                    condition=row["condition"],
                    risk_bucket=RiskBucket(decision["risk_bucket"]),
                    shown_components_count=int(decision["budget_signature"].get("shown_components_count", 0)),
                    shown_text_tokens=int(decision["budget_signature"].get("text_tokens_shown", 0)),
                    evidence_available=int(decision["budget_signature"].get("evidence_available_count", 0)),
                    max_extra_steps=int(decision["budget_signature"].get("max_extra_steps", 0)),
                    realized_extra_steps=0,
                    verification_actions=0,
                    block_id=row["block_id"],
                )
            )

        if not traces:
            return []

        observed = summarize_budgets_by_condition(traces)
        reference = {condition: dict(metrics) for condition, metrics in observed.items()}
        return compare_budget_to_reference(
            observed=observed,
            reference=reference,
            text_budget_tolerance_pct=20.0,
            interaction_budget_tolerance_pct=20.0,
            hard_max_extra_steps_per_trial=1,
        )
