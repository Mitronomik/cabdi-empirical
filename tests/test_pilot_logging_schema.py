from __future__ import annotations

import pytest

from packages.logging_schema.pilot_logs import TrialEventLog, TrialSummaryLog


def test_trial_event_log_accepts_supported_event_types():
    event = TrialEventLog(
        event_id="evt_1",
        session_id="sess_1",
        block_id="block_1",
        trial_id="trial_1",
        timestamp="2026-01-01T00:00:00",
        event_type="trial_started",
        payload={"condition": "static_help"},
    )
    encoded = event.to_dict()
    decoded = TrialEventLog.from_dict(encoded)
    assert decoded.event_type == "trial_started"


def test_trial_event_log_rejects_unsupported_event_type():
    with pytest.raises(ValueError, match="unsupported event_type"):
        TrialEventLog(
            event_id="evt_2",
            session_id="sess_1",
            block_id="block_1",
            trial_id="trial_1",
            timestamp="2026-01-01T00:00:00",
            event_type="made_up_event",
            payload={},
        ).validate()


def test_trial_summary_log_completeness_and_roundtrip():
    summary = TrialSummaryLog(
        participant_id="p1",
        session_id="s1",
        experiment_id="pilot_scam_not_scam_v1",
        condition="monotone_help",
        stimulus_id="sns_001",
        task_family="scam_not_scam",
        true_label="scam",
        human_response="scam",
        correct_or_not=True,
        model_prediction="scam",
        model_confidence="high",
        model_correct_or_not=True,
        risk_bucket="extreme",
        shown_help_level="high",
        shown_verification_level="forced",
        shown_components=["prediction", "confidence", "rationale"],
        accepted_model_advice=True,
        overrode_model=False,
        verification_required=True,
        verification_completed=True,
        reason_clicked=True,
        evidence_opened=False,
        reaction_time_ms=1800,
        self_confidence=76,
    )

    data = summary.to_dict()
    restored = TrialSummaryLog.from_dict(data)
    assert restored.correct_or_not is True
    assert "shown_components" in data


def test_trial_summary_rejects_invalid_self_confidence_range():
    with pytest.raises(ValueError, match="self_confidence"):
        TrialSummaryLog(
            participant_id="p1",
            session_id="s1",
            experiment_id="pilot_scam_not_scam_v1",
            condition="monotone_help",
            stimulus_id="sns_001",
            task_family="scam_not_scam",
            true_label="scam",
            human_response="scam",
            correct_or_not=True,
            model_prediction="scam",
            model_confidence="high",
            model_correct_or_not=True,
            risk_bucket="extreme",
            shown_help_level="high",
            shown_verification_level="forced",
            shown_components=["prediction"],
            accepted_model_advice=True,
            overrode_model=False,
            verification_required=True,
            verification_completed=True,
            reason_clicked=True,
            evidence_opened=False,
            reaction_time_ms=1200,
            self_confidence=120,
        ).validate()
