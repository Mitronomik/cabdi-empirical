"""Run the minimal reproducible human-pilot analysis pipeline (PR-6 scope)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.pilot.derive_metrics import derive_trial_level_rows, load_csv_rows, parse_event_log, write_csv
from analysis.pilot.exclusions import compute_exclusion_flags
from analysis.pilot.mixed_effects_ready import build_mixed_effects_ready
from analysis.pilot.report_builder import build_report
from analysis.pilot.summaries import build_participant_summary


def _load_optional_csv(path: str | None) -> list[dict]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    return load_csv_rows(p)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PR-6 pilot analysis pipeline")
    parser.add_argument("--trial-summary-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--event-log-jsonl")
    parser.add_argument("--session-summary-csv")
    parser.add_argument("--block-questionnaire-csv")
    parser.add_argument("--diagnostics-json")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trial_summary_rows = load_csv_rows(Path(args.trial_summary_csv))
    event_map = parse_event_log(Path(args.event_log_jsonl)) if args.event_log_jsonl else {}
    trial_level_rows, warnings = derive_trial_level_rows(trial_summary_rows, event_map)
    trial_level_path = out_dir / "trial_level.csv"
    write_csv(trial_level_rows, trial_level_path)

    session_rows = _load_optional_csv(args.session_summary_csv)
    exclusion_rows = compute_exclusion_flags(trial_level_rows, session_rows)
    exclusions_path = out_dir / "exclusion_flags.csv"
    write_csv(exclusion_rows, exclusions_path)

    questionnaire_rows = _load_optional_csv(args.block_questionnaire_csv)
    participant_rows = build_participant_summary(trial_level_rows, exclusion_rows, questionnaire_rows)
    participant_path = out_dir / "participant_summary.csv"
    write_csv(participant_rows, participant_path)

    mixed_rows = build_mixed_effects_ready(trial_level_rows, participant_rows)
    mixed_path = out_dir / "mixed_effects_ready.csv"
    write_csv(mixed_rows, mixed_path)

    diagnostics = {}
    if args.diagnostics_json and Path(args.diagnostics_json).exists():
        diagnostics = json.loads(Path(args.diagnostics_json).read_text(encoding="utf-8"))
    if warnings:
        diagnostics = dict(diagnostics)
        diagnostics.setdefault("warnings", [])
        diagnostics["warnings"].extend(warnings)

    report = build_report(trial_level_rows, participant_rows, exclusion_rows, session_rows, diagnostics)
    (out_dir / "pilot_summary.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
