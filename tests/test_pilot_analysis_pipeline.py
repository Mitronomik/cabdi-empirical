from __future__ import annotations

import csv
from pathlib import Path

from experiments.run_pilot_analysis import main as run_pipeline


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_pilot_analysis_pipeline_outputs_required_artifacts(tmp_path, monkeypatch):
    trial_summary_path = tmp_path / "trial_summary.csv"
    event_log_path = tmp_path / "events.jsonl"
    session_summary_path = tmp_path / "session_summary.csv"
    questionnaire_path = tmp_path / "questionnaire.csv"
    output_dir = tmp_path / "analysis_out"

    trial_rows = [
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
            "self_confidence": "80",
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
            "human_response": "not_scam",
            "correct_or_not": "false",
            "model_correct_or_not": "false",
            "accepted_model_advice": "true",
            "overrode_model": "false",
            "reaction_time_ms": "900",
            "self_confidence": "70",
            "verification_completed": "true",
            "verification_required": "true",
            "reason_clicked": "true",
            "evidence_opened": "true",
        },
    ]
    _write_csv(trial_summary_path, trial_rows)

    event_log_path.write_text(
        "\n".join(
            [
                '{"event_id":"e1","session_id":"s1","block_id":"block_1","trial_id":"s1_t001","timestamp":"2026-01-01T00:00:00","event_type":"trial_started","payload":{}}',
                '{"event_id":"e2","session_id":"s1","block_id":"block_1","trial_id":"s1_t002","timestamp":"2026-01-01T00:00:01","event_type":"trial_started","payload":{}}',
            ]
        ),
        encoding="utf-8",
    )

    _write_csv(
        session_summary_path,
        [{"session_id": "s1", "participant_id": "p1", "status": "completed", "experiment_id": "toy_v1"}],
    )
    _write_csv(
        questionnaire_path,
        [
            {
                "session_id": "s1",
                "block_id": "block_1",
                "burden": "30",
                "trust": "60",
                "usefulness": "70",
                "submitted_at": "2026-01-01T00:00:02",
            }
        ],
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_pilot_analysis",
            "--trial-summary-csv",
            str(trial_summary_path),
            "--event-log-jsonl",
            str(event_log_path),
            "--session-summary-csv",
            str(session_summary_path),
            "--block-questionnaire-csv",
            str(questionnaire_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    run_pipeline()

    assert (output_dir / "trial_level.csv").exists()
    assert (output_dir / "participant_summary.csv").exists()
    assert (output_dir / "mixed_effects_ready.csv").exists()
    assert (output_dir / "pilot_summary.md").exists()

    mixed_rows = list(csv.DictReader((output_dir / "mixed_effects_ready.csv").open()))
    assert {"participant", "item", "condition", "correct", "model_wrong", "followed_wrong_model", "correct_override", "log_rt"}.issubset(
        mixed_rows[0].keys()
    )

    report_text = (output_dir / "pilot_summary.md").read_text(encoding="utf-8")
    assert "N started" in report_text
    assert "under this toy pilot setup" in report_text
