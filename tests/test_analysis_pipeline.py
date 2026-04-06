from __future__ import annotations

from analysis.pilot.derive_metrics import derive_trial_level_rows
from analysis.pilot.mixed_effects_ready import build_mixed_effects_ready


def test_trial_level_includes_ordinal_confidence_and_missing_confidence_warning():
    rows, warnings = derive_trial_level_rows(
        [
            {
                "participant_id": "p1",
                "session_id": "s1",
                "experiment_id": "toy_v1",
                "condition": "static_help",
                "stimulus_id": "itm_1",
                "task_family": "scam_not_scam",
                "human_response": "scam",
                "correct_or_not": "true",
                "model_correct_or_not": "true",
                "accepted_model_advice": "true",
                "overrode_model": "false",
                "reaction_time_ms": "1000",
                "self_confidence": "3",
                "verification_completed": "false",
                "verification_required": "false",
                "reason_clicked": "false",
                "evidence_opened": "false",
            },
            {
                "participant_id": "p1",
                "session_id": "s1",
                "experiment_id": "toy_v1",
                "condition": "static_help",
                "stimulus_id": "itm_2",
                "task_family": "scam_not_scam",
                "human_response": "scam",
                "correct_or_not": "false",
                "model_correct_or_not": "false",
                "accepted_model_advice": "true",
                "overrode_model": "false",
                "reaction_time_ms": "1200",
                "self_confidence": "",
                "verification_completed": "false",
                "verification_required": "false",
                "reason_clicked": "false",
                "evidence_opened": "false",
            },
        ]
    )
    assert rows[0]["confidence"] == 3
    assert rows[1]["confidence"] is None
    assert any(w.startswith("missing_confidence:") for w in warnings)


def test_mixed_effects_ready_remains_consistent_with_trial_level_rows():
    trial_rows = [
        {
            "participant_id": "p1",
            "session_id": "s1",
            "stimulus_id": "itm_1",
            "condition": "static_help",
            "block_id": "block_1",
            "trial_id": "s1_t001",
            "order_index": "",
            "trial_index": 1,
            "correct": 1,
            "model_wrong": 0,
            "followed_wrong_model": 0,
            "correct_override": 0,
            "reaction_time_ms": 1000,
        }
    ]
    mixed = build_mixed_effects_ready(trial_rows)
    assert mixed[0]["participant"] == "p1"
    assert mixed[0]["item"] == "itm_1"
    assert "log_rt" in mixed[0]

