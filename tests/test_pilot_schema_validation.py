from __future__ import annotations

import json

import pytest

from packages.shared_types.pilot_types import (
    SESSION_STATUS_CREATED,
    SESSION_STATUS_IN_PROGRESS,
    ExperimentConfig,
    ParticipantSession,
    PolicyDecision,
    RiskBucket,
    StimulusItem,
    TrialContext,
)
from pilot.config_loader import load_all_pilot_configs
from pilot.stimulus_validation import load_stimulus_bank


def test_load_all_pilot_configs_validates_cross_file_consistency():
    loaded = load_all_pilot_configs("pilot/configs")
    exp = loaded["experiment"]
    assert isinstance(exp, ExperimentConfig)
    assert set(exp.conditions) == set(loaded["policy_conditions"].keys())
    assert exp.n_blocks == len(loaded["latin_square_orders"])


def test_stimulus_bank_validates_and_loads_demo_file():
    items = load_stimulus_bank("pilot/stimuli/scam_not_scam_demo.jsonl")
    assert len(items) == 3
    assert all(isinstance(item, StimulusItem) for item in items)


def test_stimulus_validation_rejects_duplicate_stimulus_id(tmp_path):
    duplicate_path = tmp_path / "duplicate.jsonl"
    row = {
        "stimulus_id": "dup_1",
        "task_family": "scam_not_scam",
        "content_type": "text",
        "payload": {"message": "hello"},
        "true_label": "scam",
        "difficulty_prior": "low",
        "model_prediction": "scam",
        "model_confidence": "high",
        "model_correct": True,
        "eligible_sets": ["A"],
    }
    duplicate_path.write_text(f"{json.dumps(row)}\n{json.dumps(row)}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate stimulus_id"):
        load_stimulus_bank(duplicate_path)


def test_serialization_roundtrip_for_shared_schemas():
    stim = StimulusItem(
        stimulus_id="s1",
        task_family="scam_not_scam",
        content_type="text",
        payload={"message": "demo"},
        true_label="scam",
        difficulty_prior="medium",
        model_prediction="not_scam",
        model_confidence="low",
        model_correct=False,
        eligible_sets=["A"],
    )
    ctx = TrialContext(
        session_id="sess_1",
        participant_id="p_1",
        condition="static_help",
        block_id="b_1",
        trial_id="t_1",
        stimulus=stim,
        recent_history={"recent_errors": 1},
        pre_render_features={"risk_bucket": "moderate"},
    )
    decision = PolicyDecision(
        condition="static_help",
        risk_bucket=RiskBucket.MODERATE,
        show_prediction=True,
        show_confidence=True,
        show_rationale="inline",
        show_evidence=False,
        verification_mode="soft_prompt",
        compression_mode="none",
        max_extra_steps=1,
        ui_help_level="fixed",
        ui_verification_level="fixed",
        budget_signature={"steps": 1},
    )
    session = ParticipantSession(
        session_id="sess_1",
        participant_id="p_1",
        experiment_id="pilot_scam_not_scam_v1",
        run_id="run_1",
        assigned_order="order_1",
        stimulus_set_map={"block_1": "A"},
        current_block_index=-1,
        current_trial_index=0,
        status=SESSION_STATUS_CREATED,
        started_at="2026-01-01T00:00:00",
        completed_at=None,
        device_info={"user_agent": "pytest"},
    )

    assert TrialContext.from_dict(ctx.to_dict()).trial_id == "t_1"
    assert PolicyDecision.from_dict(decision.to_dict()).risk_bucket == RiskBucket.MODERATE
    assert ParticipantSession.from_dict(session.to_dict()).session_id == "sess_1"


def test_participant_session_allows_prestart_block_index_while_in_progress_practice():
    session = ParticipantSession(
        session_id="sess_2",
        participant_id="p_2",
        experiment_id="pilot_scam_not_scam_v1",
        run_id="run_2",
        assigned_order="order_1",
        stimulus_set_map={"block_1": "A"},
        current_block_index=-1,
        current_trial_index=0,
        status=SESSION_STATUS_IN_PROGRESS,
        started_at="2026-01-01T00:00:00",
        completed_at=None,
        device_info={"user_agent": "pytest"},
    )
    session.validate()


def test_participant_session_rejects_prestart_block_index_after_trials_done():
    session = ParticipantSession(
        session_id="sess_3",
        participant_id="p_3",
        experiment_id="pilot_scam_not_scam_v1",
        run_id="run_3",
        assigned_order="order_1",
        stimulus_set_map={"block_1": "A"},
        current_block_index=-1,
        current_trial_index=0,
        status="awaiting_final_submit",
        started_at="2026-01-01T00:00:00",
        completed_at=None,
        device_info={"user_agent": "pytest"},
    )
    with pytest.raises(ValueError, match="post-trial session state requires current_block_index >= 0"):
        session.validate()
