from __future__ import annotations

import csv
from pathlib import Path

from experiments.run_toy_pilot_dry_run import REQUIRED_TRIAL_SUMMARY_FIELDS, run_dry_run


def test_pilot_end_to_end_smoke_logging_fields_present(tmp_path):
    output_dir = tmp_path / "smoke"
    summary = run_dry_run("pilot/configs/dry_run_experiment.yaml", output_dir)

    assert summary["integrity_errors"] == []

    trial_summary_path = output_dir / "raw" / "trial_summary.csv"
    with trial_summary_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    for row in rows:
        for field in REQUIRED_TRIAL_SUMMARY_FIELDS:
            assert row.get(field) not in {None, ""}

    diagnostics_path = output_dir / "raw" / "diagnostics.json"
    diagnostics_text = diagnostics_path.read_text(encoding="utf-8")
    assert "budget_tolerance_flags" in diagnostics_text

    analysis_summary = Path(output_dir / "analysis" / "pilot_summary.md").read_text(encoding="utf-8")
    assert "under this toy pilot setup" in analysis_summary
