"""Pilot policy runtime rules for human-pilot mode.

This module computes pre-render risk buckets and returns structured PolicyDecision
objects consumable by future API/UI layers.
"""

from __future__ import annotations

from typing import Any

from packages.shared_types.pilot_types import PolicyDecision, RiskBucket, TrialContext
from pilot.config_loader import load_policy_conditions
from policies.contracts import PreRenderRiskFeatures, TrialRiskState


DEFAULT_POLICY_CONDITIONS_PATH = "pilot/configs/policy_conditions.yaml"


def _count_instability_markers(features: PreRenderRiskFeatures) -> int:
    markers = 0
    if features.recent_error_count_last_3 >= 2:
        markers += 1
    if features.recent_blind_accept_count_last_3 >= 1:
        markers += 1
    if features.recent_latency_z_bucket == "high":
        markers += 1
    return markers


def assign_risk_bucket_v1(features: PreRenderRiskFeatures) -> RiskBucket:
    """Assign pre-render risk bucket from explicit v1 rules.

    Rule summary:
    - extreme: low confidence OR (high difficulty + recent blind acceptance) OR >=2 instability markers
    - low: high confidence + low/medium difficulty + no instability markers
    - moderate: otherwise
    """
    instability_markers = _count_instability_markers(features)

    if (
        features.model_confidence == "low"
        or (
            features.difficulty_prior == "high"
            and features.recent_blind_accept_count_last_3 >= 1
        )
        or instability_markers >= 2
    ):
        return RiskBucket.EXTREME

    if (
        features.model_confidence == "high"
        and features.difficulty_prior in {"low", "medium"}
        and instability_markers == 0
    ):
        return RiskBucket.LOW

    return RiskBucket.MODERATE


def get_or_assign_trial_risk_state(
    trial_context: TrialContext,
    existing_state: TrialRiskState | None = None,
) -> TrialRiskState:
    """Return frozen risk state; reject within-trial recomputation attempts."""
    if existing_state is not None:
        if existing_state.trial_id != trial_context.trial_id:
            raise ValueError("existing TrialRiskState trial_id does not match trial_context")
        return existing_state

    features = PreRenderRiskFeatures.from_mapping(
        {
            "model_confidence": trial_context.pre_render_features.get(
                "model_confidence", trial_context.stimulus.model_confidence
            ),
            "difficulty_prior": trial_context.pre_render_features.get(
                "difficulty_prior", trial_context.stimulus.difficulty_prior
            ),
            "recent_error_count_last_3": trial_context.pre_render_features.get("recent_error_count_last_3", 0),
            "recent_blind_accept_count_last_3": trial_context.pre_render_features.get(
                "recent_blind_accept_count_last_3", 0
            ),
            "recent_latency_z_bucket": trial_context.pre_render_features.get("recent_latency_z_bucket", "medium"),
        }
    )
    risk_bucket = assign_risk_bucket_v1(features)
    return TrialRiskState(trial_id=trial_context.trial_id, risk_bucket=risk_bucket)


def _policy_decision_by_condition(condition: str, risk_bucket: RiskBucket) -> dict[str, Any]:
    if condition == "static_help":
        return {
            "show_prediction": True,
            "show_confidence": True,
            "show_rationale": "inline",
            "show_evidence": False,
            "verification_mode": "none",
            "compression_mode": "none",
            "max_extra_steps": 0,
        }

    if condition == "monotone_help":
        if risk_bucket == RiskBucket.LOW:
            return {
                "show_prediction": True,
                "show_confidence": False,
                "show_rationale": "none",
                "show_evidence": False,
                "verification_mode": "none",
                "compression_mode": "none",
                "max_extra_steps": 0,
            }
        if risk_bucket == RiskBucket.MODERATE:
            return {
                "show_prediction": True,
                "show_confidence": True,
                "show_rationale": "inline",
                "show_evidence": False,
                "verification_mode": "none",
                "compression_mode": "none",
                "max_extra_steps": 0,
            }
        return {
            "show_prediction": True,
            "show_confidence": True,
            "show_rationale": "inline",
            "show_evidence": True,
            "verification_mode": "soft_prompt",
            "compression_mode": "none",
            "max_extra_steps": 0,
        }

    if condition == "cabdi_lite":
        if risk_bucket == RiskBucket.LOW:
            return {
                "show_prediction": True,
                "show_confidence": False,
                "show_rationale": "none",
                "show_evidence": False,
                "verification_mode": "none",
                "compression_mode": "none",
                "max_extra_steps": 0,
            }
        if risk_bucket == RiskBucket.MODERATE:
            return {
                "show_prediction": True,
                "show_confidence": True,
                "show_rationale": "inline",
                "show_evidence": False,
                "verification_mode": "soft_prompt",
                "compression_mode": "none",
                "max_extra_steps": 0,
            }
        return {
            "show_prediction": True,
            "show_confidence": True,
            "show_rationale": "on_click",
            "show_evidence": False,
            "verification_mode": "forced_checkbox",
            "compression_mode": "medium",
            "max_extra_steps": 1,
        }

    raise ValueError(f"Unknown pilot policy condition: {condition}")


def expected_budget_signature(condition: str, risk_bucket: RiskBucket) -> dict[str, int]:
    """Return the contract budget signature for a condition/risk pair."""
    decision_kwargs = _policy_decision_by_condition(condition, risk_bucket)
    shown_components_count = sum(
        int(flag)
        for flag in [
            decision_kwargs["show_prediction"],
            decision_kwargs["show_confidence"],
            decision_kwargs["show_rationale"] != "none",
            decision_kwargs["show_evidence"],
        ]
    )
    rationale_load_units = 0
    if decision_kwargs["show_rationale"] == "inline":
        rationale_load_units = 2
    elif decision_kwargs["show_rationale"] == "on_click":
        rationale_load_units = 1
    verification_load_units = {
        "none": 0,
        "soft_prompt": 1,
        "forced_checkbox": 2,
        "forced_second_look": 3,
    }[decision_kwargs["verification_mode"]]
    compression_factor = {"none": 1.0, "medium": 0.85, "high": 0.7}[decision_kwargs["compression_mode"]]
    display_load_units = int(
        round(
            (
                (2 if decision_kwargs["show_prediction"] else 0)
                + (1 if decision_kwargs["show_confidence"] else 0)
                + rationale_load_units
                + (2 if decision_kwargs["show_evidence"] else 0)
            )
            * compression_factor
        )
    )
    interaction_load_units = decision_kwargs["max_extra_steps"] + verification_load_units
    return {
        "shown_components_count": shown_components_count,
        "text_tokens_shown": int(20 * shown_components_count),
        "evidence_available_count": int(decision_kwargs["show_evidence"]),
        "max_extra_steps": int(decision_kwargs["max_extra_steps"]),
        # v2 semantics: keep legacy keys above while adding interpretable units.
        "display_load_units": int(display_load_units),
        "interaction_load_units": int(interaction_load_units),
        "verification_load_units": int(verification_load_units),
        "provenance_cue_units": int(
            int(decision_kwargs["show_confidence"])
            + int(decision_kwargs["show_rationale"] != "none")
            + int(decision_kwargs["show_evidence"])
        ),
    }


def build_policy_decision(
    trial_context: TrialContext,
    trial_risk_state: TrialRiskState,
    policy_conditions_path: str = DEFAULT_POLICY_CONDITIONS_PATH,
    budget_overrides: dict[str, Any] | None = None,
) -> PolicyDecision:
    """Build structured PolicyDecision for condition + frozen risk bucket."""
    if trial_risk_state.trial_id != trial_context.trial_id:
        raise ValueError("trial_risk_state must belong to the same trial")

    condition_map = load_policy_conditions(policy_conditions_path)
    if trial_context.condition not in condition_map:
        raise ValueError(f"Condition {trial_context.condition} missing from policy config")

    condition_spec = condition_map[trial_context.condition]
    decision_kwargs = _policy_decision_by_condition(trial_context.condition, trial_risk_state.risk_bucket)

    budget_signature = expected_budget_signature(trial_context.condition, trial_risk_state.risk_bucket)
    if budget_overrides:
        budget_signature = replace_budget_signature(budget_signature, budget_overrides)

    return PolicyDecision(
        condition=trial_context.condition,
        risk_bucket=trial_risk_state.risk_bucket,
        ui_help_level=str(condition_spec["ui_help_level"]),
        ui_verification_level=str(condition_spec["ui_verification_level"]),
        budget_signature=budget_signature,
        **decision_kwargs,
    )


def replace_budget_signature(base_signature: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Pure helper that applies deterministic budget signature overrides."""
    out = dict(base_signature)
    out.update(overrides)
    return out
