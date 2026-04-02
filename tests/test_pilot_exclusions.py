from __future__ import annotations

from analysis.pilot.exclusions import compute_exclusion_flags


def test_exclusion_flags_detect_fast_and_repeated_patterns():
    rows = []
    for i in range(12):
        rows.append(
            {
                "session_id": "s1",
                "participant_id": "p1",
                "trial_id": f"s1_t{i:03d}",
                "stimulus_id": f"i{i}",
                "reaction_time_ms": "120",
                "confidence": "",
                "followed_model": "1",
                "correct": "1",
            }
        )

    flags = compute_exclusion_flags(
        rows,
        session_summary_rows=[{"session_id": "s1", "participant_id": "p1", "status": "in_progress"}],
        too_fast_median_ms=200,
        missing_confidence_threshold=0.1,
    )
    assert len(flags) == 1
    row = flags[0]
    assert row["too_fast_responder"] is True
    assert row["missing_confidence_reports"] is True
    assert row["incomplete_session"] is True
    assert row["repeated_same_response_pattern"] is True
    assert row["logging_corruption_flag"] is False
