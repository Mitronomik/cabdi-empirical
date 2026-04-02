from __future__ import annotations

from pathlib import Path

from experiments.run_toy_pilot_dry_run import run_dry_run


def test_pilot_dry_run_generates_required_artifacts(tmp_path):
    output_dir = tmp_path / "dry_run_outputs"
    summary = run_dry_run("pilot/configs/dry_run_experiment.yaml", output_dir)

    assert summary["integrity_errors"] == []
    assert (output_dir / "pilot_dry_run.md").exists()
    assert (output_dir / "dry_run_summary.json").exists()

    assert (output_dir / "raw" / "raw_event_log.jsonl").exists()
    assert (output_dir / "raw" / "trial_summary.csv").exists()

    assert (output_dir / "analysis" / "trial_level.csv").exists()
    assert (output_dir / "analysis" / "participant_summary.csv").exists()
    assert (output_dir / "analysis" / "mixed_effects_ready.csv").exists()

    report_text = (output_dir / "pilot_dry_run.md").read_text(encoding="utf-8")
    assert "does **not** substitute for human-participant data" in report_text

    event_log = (output_dir / "raw" / "raw_event_log.jsonl").read_text(encoding="utf-8").strip()
    assert event_log
    assert "trial_completed" in event_log


def test_pilot_dry_run_reproducible_structure(tmp_path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"

    run_dry_run("pilot/configs/dry_run_experiment.yaml", out_a)
    run_dry_run("pilot/configs/dry_run_experiment.yaml", out_b)

    report_a = (out_a / "pilot_dry_run.md").read_text(encoding="utf-8")
    report_b = (out_b / "pilot_dry_run.md").read_text(encoding="utf-8")

    # Stable structural checks (ignore run_id/session IDs and timestamps).
    for needle in ["Sessions simulated: `5`", "Per-condition trial counts", "Integrity errors: `0`"]:
        assert needle in report_a
        assert needle in report_b

    trial_level_a = Path(out_a / "analysis" / "trial_level.csv").read_text(encoding="utf-8").splitlines()
    trial_level_b = Path(out_b / "analysis" / "trial_level.csv").read_text(encoding="utf-8").splitlines()
    assert len(trial_level_a) == len(trial_level_b)
