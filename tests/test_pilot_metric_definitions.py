from __future__ import annotations

import pytest

from analysis.pilot.derive_metrics import derive_trial_level_rows
from analysis.pilot.summaries import build_participant_summary


def test_metric_formulas_for_reliance_and_overrides():
    trial_rows = [
        {
            "participant_id": "p1",
            "session_id": "s1",
            "experiment_id": "toy_v1",
            "condition": "cabdi_lite",
            "stimulus_id": "i1",
            "task_family": "scam_not_scam",
            "human_response": "a",
            "correct_or_not": "true",
            "model_correct_or_not": "false",
            "accepted_model_advice": "false",
            "overrode_model": "true",
            "reaction_time_ms": "1000",
            "self_confidence": "3",
            "verification_completed": "true",
            "verification_required": "true",
            "reason_clicked": "true",
            "evidence_opened": "false",
        },
        {
            "participant_id": "p1",
            "session_id": "s1",
            "experiment_id": "toy_v1",
            "condition": "cabdi_lite",
            "stimulus_id": "i2",
            "task_family": "scam_not_scam",
            "human_response": "b",
            "correct_or_not": "false",
            "model_correct_or_not": "false",
            "accepted_model_advice": "true",
            "overrode_model": "false",
            "reaction_time_ms": "1100",
            "self_confidence": "3",
            "verification_completed": "false",
            "verification_required": "true",
            "reason_clicked": "false",
            "evidence_opened": "true",
        },
        {
            "participant_id": "p1",
            "session_id": "s1",
            "experiment_id": "toy_v1",
            "condition": "cabdi_lite",
            "stimulus_id": "i3",
            "task_family": "scam_not_scam",
            "human_response": "c",
            "correct_or_not": "true",
            "model_correct_or_not": "true",
            "accepted_model_advice": "true",
            "overrode_model": "false",
            "reaction_time_ms": "900",
            "self_confidence": "4",
            "verification_completed": "false",
            "verification_required": "false",
            "reason_clicked": "false",
            "evidence_opened": "false",
        },
    ]

    derived, warnings = derive_trial_level_rows(trial_rows)
    assert warnings == []
    assert sum(int(r["followed_wrong_model"]) for r in derived) == 1
    assert sum(int(r["correct_override"]) for r in derived) == 1

    exclusions = [
        {
            "session_id": "s1",
            "participant_id": "p1",
            "too_fast_responder": False,
            "missing_confidence_reports": False,
            "incomplete_session": False,
            "repeated_same_response_pattern": False,
            "logging_corruption_flag": False,
        }
    ]
    summary = build_participant_summary(derived, exclusions)
    row = summary[0]
    assert row["commission_error_rate"] == pytest.approx(1 / 3)
    assert row["correct_override_rate"] == 0.5
    assert row["appropriate_reliance_proxy"] == 0.5
