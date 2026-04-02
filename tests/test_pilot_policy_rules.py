from __future__ import annotations

from packages.shared_types.pilot_types import RiskBucket, StimulusItem, TrialContext
from policies.pilot_rules import (
    build_policy_decision,
    get_or_assign_trial_risk_state,
)


def _make_context(
    condition: str,
    trial_id: str,
    *,
    model_confidence: str,
    difficulty_prior: str,
    recent_error_count_last_3: int = 0,
    recent_blind_accept_count_last_3: int = 0,
    recent_latency_z_bucket: str = "medium",
) -> TrialContext:
    stim = StimulusItem(
        stimulus_id=f"stim_{trial_id}",
        task_family="scam_not_scam",
        content_type="text",
        payload={"message": "demo"},
        true_label="scam",
        difficulty_prior=difficulty_prior,
        model_prediction="scam",
        model_confidence=model_confidence,
        model_correct=True,
        eligible_sets=["A"],
    )
    return TrialContext(
        session_id="sess_1",
        participant_id="p_1",
        condition=condition,
        block_id="b_1",
        trial_id=trial_id,
        stimulus=stim,
        recent_history={},
        pre_render_features={
            "model_confidence": model_confidence,
            "difficulty_prior": difficulty_prior,
            "recent_error_count_last_3": recent_error_count_last_3,
            "recent_blind_accept_count_last_3": recent_blind_accept_count_last_3,
            "recent_latency_z_bucket": recent_latency_z_bucket,
        },
    )


def test_static_help_invariant_across_risk_buckets():
    low_ctx = _make_context("static_help", "t_low", model_confidence="high", difficulty_prior="low")
    moderate_ctx = _make_context("static_help", "t_mod", model_confidence="medium", difficulty_prior="low")
    extreme_ctx = _make_context(
        "static_help",
        "t_ext",
        model_confidence="low",
        difficulty_prior="high",
        recent_blind_accept_count_last_3=1,
    )

    decisions = []
    for ctx in (low_ctx, moderate_ctx, extreme_ctx):
        risk_state = get_or_assign_trial_risk_state(ctx)
        decisions.append(build_policy_decision(ctx, risk_state))

    baseline = decisions[0]
    for decision in decisions[1:]:
        assert decision.show_prediction == baseline.show_prediction
        assert decision.show_confidence == baseline.show_confidence
        assert decision.show_rationale == baseline.show_rationale
        assert decision.show_evidence == baseline.show_evidence
        assert decision.verification_mode == baseline.verification_mode
        assert decision.compression_mode == baseline.compression_mode
        assert decision.max_extra_steps == baseline.max_extra_steps


def test_monotone_help_escalates_by_risk_bucket_low_to_extreme():
    contexts = {
        "low": _make_context("monotone_help", "t1", model_confidence="high", difficulty_prior="low"),
        "moderate": _make_context("monotone_help", "t2", model_confidence="medium", difficulty_prior="low"),
        "extreme": _make_context(
            "monotone_help",
            "t3",
            model_confidence="low",
            difficulty_prior="high",
            recent_blind_accept_count_last_3=1,
        ),
    }

    decisions = {
        label: build_policy_decision(ctx, get_or_assign_trial_risk_state(ctx))
        for label, ctx in contexts.items()
    }

    assert decisions["low"].show_confidence is False
    assert decisions["moderate"].show_confidence is True
    assert decisions["extreme"].show_evidence is True
    assert decisions["extreme"].verification_mode == "soft_prompt"


def test_cabdi_lite_extreme_materially_differs_from_monotone_extreme():
    monotone_ctx = _make_context(
        "monotone_help",
        "t4",
        model_confidence="low",
        difficulty_prior="high",
        recent_blind_accept_count_last_3=1,
    )
    cabdi_ctx = _make_context(
        "cabdi_lite",
        "t5",
        model_confidence="low",
        difficulty_prior="high",
        recent_blind_accept_count_last_3=1,
    )

    monotone_extreme = build_policy_decision(monotone_ctx, get_or_assign_trial_risk_state(monotone_ctx))
    cabdi_extreme = build_policy_decision(cabdi_ctx, get_or_assign_trial_risk_state(cabdi_ctx))

    assert monotone_extreme.risk_bucket == RiskBucket.EXTREME
    assert cabdi_extreme.risk_bucket == RiskBucket.EXTREME
    assert monotone_extreme.show_rationale == "inline"
    assert cabdi_extreme.show_rationale == "on_click"
    assert monotone_extreme.show_evidence is True
    assert cabdi_extreme.show_evidence is False
    assert cabdi_extreme.verification_mode == "forced_checkbox"
    assert cabdi_extreme.compression_mode == "medium"
    assert cabdi_extreme.max_extra_steps == 1


def test_no_within_trial_risk_recomputation_when_state_already_exists():
    ctx = _make_context("cabdi_lite", "t6", model_confidence="high", difficulty_prior="low")
    first_state = get_or_assign_trial_risk_state(ctx)
    assert first_state.risk_bucket == RiskBucket.LOW

    ctx.pre_render_features["model_confidence"] = "low"
    ctx.pre_render_features["difficulty_prior"] = "high"
    ctx.pre_render_features["recent_blind_accept_count_last_3"] = 2

    second_state = get_or_assign_trial_risk_state(ctx, existing_state=first_state)
    assert second_state is first_state
    assert second_state.risk_bucket == RiskBucket.LOW


def test_policy_decision_is_reproducible_and_config_driven_ui_levels():
    ctx = _make_context("cabdi_lite", "t7", model_confidence="medium", difficulty_prior="medium")
    risk_state = get_or_assign_trial_risk_state(ctx)

    d1 = build_policy_decision(ctx, risk_state)
    d2 = build_policy_decision(ctx, risk_state)

    assert d1.to_dict() == d2.to_dict()
    assert d1.ui_help_level == "regime_aware_non_monotone"
    assert d1.ui_verification_level == "targeted_extreme"
