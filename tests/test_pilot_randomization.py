from __future__ import annotations

from app.participant_api.services.randomization_service import assign_order_id, build_trial_plan
from packages.shared_types.pilot_types import ExperimentConfig, StimulusItem


def test_assigned_order_is_reproducible_for_same_participant():
    first = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    second = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    assert first == second


def test_assigned_order_is_valid_latin_square_row():
    order_id, order = assign_order_id("p_002", "pilot_scam_not_scam_v1")
    assert order_id.startswith("order_")
    assert set(order) == {"static_help", "monotone_help", "cabdi_lite"}


def test_trial_plan_pre_render_features_contain_only_pre_known_stimulus_priors():
    experiment = ExperimentConfig(
        experiment_id="toy_v1",
        task_family="scam_detection",
        n_blocks=1,
        trials_per_block=1,
        practice_trials=0,
        conditions=["cabdi_lite"],
        block_order_strategy="latin_square",
        budget_matching_mode="fixed",
        risk_proxy_mode="pre_render_features_v1",
        self_confidence_scale="0_100",
        block_questionnaires=[],
    )
    stimulus = StimulusItem(
        stimulus_id="s1",
        task_family="scam_detection",
        content_type="text",
        payload={"title": "Case"},
        true_label="scam",
        difficulty_prior="low",
        model_prediction="scam",
        model_confidence="high",
        model_correct=True,
        eligible_sets=["demo"],
    )

    plan = build_trial_plan("p_001", experiment, ["cabdi_lite"], [stimulus])
    features = plan[0]["pre_render_features"]
    assert features == {"model_confidence": "high", "difficulty_prior": "low"}
