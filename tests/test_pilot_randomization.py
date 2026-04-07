from __future__ import annotations

from app.participant_api.services.randomization_service import assign_order_id, build_trial_plan
from packages.shared_types.pilot_types import ExperimentConfig, StimulusItem


def _experiment(*, n_blocks: int = 3, trials_per_block: int = 3, practice_trials: int = 2) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id="toy_v1",
        task_family="scam_detection",
        n_blocks=n_blocks,
        trials_per_block=trials_per_block,
        practice_trials=practice_trials,
        conditions=["static_help", "monotone_help", "cabdi_lite"],
        block_order_strategy="latin_square",
        budget_matching_mode="fixed",
        risk_proxy_mode="pre_render_features_v1",
        self_confidence_scale="4_point",
        block_questionnaires=[],
    )


def _stimulus(stimulus_id: str, *, difficulty: str, model_correct: bool) -> StimulusItem:
    return StimulusItem(
        stimulus_id=stimulus_id,
        task_family="scam_detection",
        content_type="text",
        payload={"title": f"Case {stimulus_id}"},
        true_label="scam" if not model_correct else "not_scam",
        difficulty_prior=difficulty,
        model_prediction="not_scam" if model_correct else "scam",
        model_confidence="high",
        model_correct=model_correct,
        eligible_sets=["demo"],
    )


def _balanced_bank() -> list[StimulusItem]:
    items: list[StimulusItem] = []
    idx = 0
    for difficulty in ["low", "medium", "high"]:
        for model_correct in [True, False]:
            for _ in range(2):
                idx += 1
                items.append(_stimulus(f"s{idx}", difficulty=difficulty, model_correct=model_correct))
    return items


def test_assigned_order_is_reproducible_for_same_participant():
    first = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    second = assign_order_id("p_001", "pilot_scam_not_scam_v1")
    assert first == second


def test_assigned_order_is_valid_latin_square_row():
    order_id, order = assign_order_id("p_002", "pilot_scam_not_scam_v1")
    assert order_id.startswith("order_")
    assert set(order) == {"static_help", "monotone_help", "cabdi_lite"}


def test_trial_plan_pre_render_features_contain_only_pre_known_stimulus_priors():
    experiment = _experiment(n_blocks=1, trials_per_block=1, practice_trials=0)
    stimulus = _stimulus("s1", difficulty="low", model_correct=True)

    plan = build_trial_plan("p_001", experiment, ["cabdi_lite"], [stimulus])
    features = plan[0]["pre_render_features"]
    assert features["model_confidence"] == "high"
    assert features["difficulty_prior"] == "low"


def test_trial_plan_is_deterministic_for_same_seed_inputs():
    experiment = _experiment()
    stimuli = _balanced_bank()

    first = build_trial_plan("p_deterministic", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)
    second = build_trial_plan("p_deterministic", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)

    assert first == second


def test_main_trials_do_not_repeat_stimuli_when_supply_is_sufficient():
    experiment = _experiment(n_blocks=2, trials_per_block=3, practice_trials=2)
    stimuli = _balanced_bank()

    plan = build_trial_plan("p_unique", experiment, ["static_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]
    stimulus_ids = [row["stimulus"]["stimulus_id"] for row in main_trials]

    assert len(stimulus_ids) == len(set(stimulus_ids))
    assert all(not row["pre_render_features"]["allocation_reused_stimulus"] for row in main_trials)


def test_model_wrong_is_evenly_distributed_across_blocks_when_available():
    experiment = _experiment(n_blocks=3, trials_per_block=3, practice_trials=0)
    stimuli = _balanced_bank()

    plan = build_trial_plan("p_model_wrong", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]

    wrong_by_block: dict[int, int] = {0: 0, 1: 0, 2: 0}
    for row in main_trials:
        if not row["stimulus"]["model_correct"]:
            wrong_by_block[row["block_index"]] += 1
    # Main allocator targets a bounded 1/3 model-wrong share by default (3 of 9 here).
    assert sum(wrong_by_block.values()) == 3
    assert max(wrong_by_block.values()) - min(wrong_by_block.values()) <= 1


def test_difficulty_mix_is_controlled_per_block_under_normal_supply():
    experiment = _experiment(n_blocks=3, trials_per_block=3, practice_trials=0)
    stimuli = _balanced_bank()

    plan = build_trial_plan("p_difficulty", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]

    for block_index in range(3):
        block_rows = [row for row in main_trials if row["block_index"] == block_index]
        difficulties = {row["stimulus"]["difficulty_prior"] for row in block_rows}
        assert len(difficulties) >= 2
    overall_difficulties = {row["stimulus"]["difficulty_prior"] for row in main_trials}
    assert overall_difficulties == {"low", "medium", "high"}


def test_model_wrong_abundance_is_capped_instead_of_saturating_main_trials():
    experiment = _experiment(n_blocks=3, trials_per_block=3, practice_trials=0)
    stimuli = [
        *[_stimulus(f"w{i}", difficulty=["low", "medium", "high"][i % 3], model_correct=False) for i in range(1, 13)],
        *[_stimulus(f"c{i}", difficulty=["low", "medium", "high"][i % 3], model_correct=True) for i in range(1, 13)],
    ]

    plan = build_trial_plan("p_wrong_cap", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]
    wrong_count = sum(1 for row in main_trials if not row["stimulus"]["model_correct"])
    wrong_by_block = {
        block_index: sum(
            1 for row in main_trials if row["block_index"] == block_index and not row["stimulus"]["model_correct"]
        )
        for block_index in range(3)
    }

    assert wrong_count == 3
    assert max(wrong_by_block.values()) - min(wrong_by_block.values()) <= 1
    assert all(
        row["pre_render_features"]["allocation_model_wrong_target"] <= 1
        for row in main_trials
    )


def test_model_wrong_low_supply_is_used_honestly_and_evenly():
    experiment = _experiment(n_blocks=3, trials_per_block=3, practice_trials=0)
    stimuli = [
        _stimulus("w1", difficulty="low", model_correct=False),
        _stimulus("w2", difficulty="high", model_correct=False),
        *[_stimulus(f"c{i}", difficulty=["low", "medium", "high"][i % 3], model_correct=True) for i in range(1, 11)],
    ]

    plan = build_trial_plan("p_wrong_low_supply", experiment, ["static_help", "monotone_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]
    wrong_count = sum(1 for row in main_trials if not row["stimulus"]["model_correct"])
    wrong_by_block = {
        block_index: sum(
            1 for row in main_trials if row["block_index"] == block_index and not row["stimulus"]["model_correct"]
        )
        for block_index in range(3)
    }

    assert wrong_count == 2
    assert max(wrong_by_block.values()) - min(wrong_by_block.values()) <= 1


def test_insufficient_main_bank_uses_explicit_deterministic_reuse():
    experiment = _experiment(n_blocks=2, trials_per_block=3, practice_trials=0)
    stimuli = [_stimulus("s1", difficulty="low", model_correct=True), _stimulus("s2", difficulty="high", model_correct=False)]

    plan = build_trial_plan("p_small_bank", experiment, ["static_help", "cabdi_lite"], stimuli)
    main_trials = [row for row in plan if row["block_index"] >= 0]
    ids = [row["stimulus"]["stimulus_id"] for row in main_trials]

    assert len(set(ids)) < len(ids)
    assert all(row["pre_render_features"]["allocation_reused_stimulus"] for row in main_trials)


def test_practice_allocation_is_separate_and_stable():
    experiment = _experiment(n_blocks=1, trials_per_block=1, practice_trials=2)
    stimuli = [
        _stimulus("s1", difficulty="high", model_correct=False),
        _stimulus("s2", difficulty="medium", model_correct=True),
        _stimulus("s3", difficulty="low", model_correct=True),
    ]

    plan = build_trial_plan("p_practice", experiment, ["cabdi_lite"], stimuli)
    practice = [row for row in plan if row["block_index"] == -1]
    main = [row for row in plan if row["block_index"] >= 0]

    assert len(practice) == 2
    assert all(row["pre_render_features"]["allocation_phase"] == "practice" for row in practice)
    assert all(row["pre_render_features"]["allocation_phase"] == "main" for row in main)
    assert practice[0]["condition"] == "static_help"
