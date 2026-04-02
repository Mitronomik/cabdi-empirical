"""Budget diagnostics for pilot policy runtime.

Implements display and interaction budget summaries with tolerance checks.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from statistics import mean
from typing import Any

from policies.contracts import BudgetTrace


def summarize_budgets_by_condition(traces: list[BudgetTrace]) -> dict[str, dict[str, float]]:
    """Aggregate display and interaction budget metrics per condition."""
    grouped: dict[str, list[BudgetTrace]] = defaultdict(list)
    for trace in traces:
        grouped[trace.condition].append(trace)

    summary: dict[str, dict[str, float]] = {}
    for condition, rows in grouped.items():
        summary[condition] = {
            "trials": float(len(rows)),
            "mean_shown_components_count": mean(r.shown_components_count for r in rows),
            "mean_text_tokens_shown": mean(r.shown_text_tokens for r in rows),
            "evidence_availability_count": float(sum(r.evidence_available for r in rows)),
            "max_extra_steps_per_trial": float(max(r.max_extra_steps for r in rows)),
            "mean_realized_extra_steps": mean(r.realized_extra_steps for r in rows),
            "verification_actions_per_block": float(sum(r.verification_actions for r in rows)),
        }
    return summary


def summarize_interaction_by_block(traces: list[BudgetTrace]) -> dict[str, dict[str, float]]:
    """Aggregate interaction budget metrics per block."""
    grouped: dict[str, list[BudgetTrace]] = defaultdict(list)
    for trace in traces:
        block_id = trace.block_id or "__no_block__"
        grouped[block_id].append(trace)

    out: dict[str, dict[str, float]] = {}
    for block_id, rows in grouped.items():
        out[block_id] = {
            "trials": float(len(rows)),
            "mean_extra_steps": mean(r.realized_extra_steps for r in rows),
            "verification_actions": float(sum(r.verification_actions for r in rows)),
        }
    return out


def compare_budget_to_reference(
    observed: dict[str, dict[str, float]],
    reference: dict[str, dict[str, float]],
    text_budget_tolerance_pct: float,
    interaction_budget_tolerance_pct: float,
    hard_max_extra_steps_per_trial: int,
) -> list[dict[str, Any]]:
    """Emit warning flags when observed budget deviates from reference/tolerances."""
    flags: list[dict[str, Any]] = []
    tol_text = text_budget_tolerance_pct / 100.0
    tol_interaction = interaction_budget_tolerance_pct / 100.0

    for condition, obs in observed.items():
        ref = reference.get(condition)
        if ref is None:
            flags.append(
                {
                    "condition": condition,
                    "severity": "warning",
                    "kind": "missing_reference",
                    "message": "No reference budget found for condition",
                }
            )
            continue

        text_obs = float(obs["mean_text_tokens_shown"])
        text_ref = float(ref["mean_text_tokens_shown"])
        if text_ref > 0 and abs(text_obs - text_ref) / text_ref > tol_text:
            flags.append(
                {
                    "condition": condition,
                    "severity": "warning",
                    "kind": "text_tolerance_exceeded",
                    "observed": text_obs,
                    "reference": text_ref,
                }
            )

        step_obs = float(obs["mean_realized_extra_steps"])
        step_ref = float(ref["mean_realized_extra_steps"])
        denom = step_ref if step_ref > 0 else 1.0
        if abs(step_obs - step_ref) / denom > tol_interaction:
            flags.append(
                {
                    "condition": condition,
                    "severity": "warning",
                    "kind": "interaction_tolerance_exceeded",
                    "observed": step_obs,
                    "reference": step_ref,
                }
            )

        if float(obs["max_extra_steps_per_trial"]) > hard_max_extra_steps_per_trial:
            flags.append(
                {
                    "condition": condition,
                    "severity": "error",
                    "kind": "hard_cap_exceeded",
                    "observed": float(obs["max_extra_steps_per_trial"]),
                    "cap": hard_max_extra_steps_per_trial,
                }
            )

    return flags


def budget_trace_from_decision(
    *,
    condition: str,
    risk_bucket: str,
    budget_signature: dict[str, Any],
    realized_extra_steps: int,
    verification_actions: int,
    block_id: str | None,
) -> BudgetTrace:
    """Create BudgetTrace from a policy decision + realized interaction info."""
    from packages.shared_types.pilot_types import RiskBucket

    return BudgetTrace(
        condition=condition,
        risk_bucket=RiskBucket(risk_bucket),
        shown_components_count=int(budget_signature["shown_components_count"]),
        shown_text_tokens=int(budget_signature["text_tokens_shown"]),
        evidence_available=int(budget_signature["evidence_available_count"]),
        max_extra_steps=int(budget_signature["max_extra_steps"]),
        realized_extra_steps=int(realized_extra_steps),
        verification_actions=int(verification_actions),
        block_id=block_id,
    )


def serialize_budget_traces(traces: list[BudgetTrace]) -> list[dict[str, Any]]:
    """Serialize budget traces for future logging/export layers."""
    serialized = []
    for trace in traces:
        row = asdict(trace)
        row["risk_bucket"] = trace.risk_bucket.value
        serialized.append(row)
    return serialized
