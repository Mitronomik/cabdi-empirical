"""Markdown report builder for toy pilot analysis outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

_SIGNAL_NOTE = (
    "These outputs are from a toy human-pilot setup and should be interpreted as "
    "behavior-first observational signals, not whole-framework validation."
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_report(
    trial_level_rows: list[dict[str, Any]],
    participant_summary_rows: list[dict[str, Any]],
    exclusions_rows: list[dict[str, Any]],
    session_summary_rows: list[dict[str, Any]] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    session_summary_rows = session_summary_rows or []
    diagnostics = diagnostics or {}

    started = len(session_summary_rows) if session_summary_rows else len({r.get("session_id") for r in trial_level_rows})
    completed = (
        sum(1 for r in session_summary_rows if str(r.get("status", "")) == "completed")
        if session_summary_rows
        else len({r.get("session_id") for r in trial_level_rows})
    )
    excluded_flagged = sum(
        1
        for row in exclusions_rows
        if any(
            str(row.get(flag, "")).lower() == "true"
            for flag in [
                "too_fast_responder",
                "missing_confidence_reports",
                "incomplete_session",
                "repeated_same_response_pattern",
                "logging_corruption_flag",
            ]
        )
    )
    task_families = sorted({str(r.get("task_family", "unknown")) for r in trial_level_rows})

    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in participant_summary_rows:
        by_condition[str(row.get("condition", "unknown"))].append(row)

    condition_lines = [
        "| condition | utility_accuracy | commission_error_rate | correct_override_rate | appropriate_reliance_proxy | mean_rt |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for condition, rows in sorted(by_condition.items()):
        utility = mean(float(r.get("utility_accuracy", 0.0) or 0.0) for r in rows)
        commission = mean(float(r.get("commission_error_rate", 0.0) or 0.0) for r in rows)
        override = mean(float(r.get("correct_override_rate", 0.0) or 0.0) for r in rows)
        reliance = mean(float(r.get("appropriate_reliance_proxy", 0.0) or 0.0) for r in rows)
        mean_rt = mean(float(r.get("mean_rt", 0.0) or 0.0) for r in rows)
        condition_lines.append(
            f"| {condition} | {utility:.3f} | {commission:.3f} | {override:.3f} | {reliance:.3f} | {mean_rt:.1f} |"
        )

    warnings = []
    warnings.extend(diagnostics.get("warnings", []))
    if diagnostics.get("budget_tolerance_flags"):
        warnings.append(f"budget_tolerance_flags={len(diagnostics['budget_tolerance_flags'])}")
    if not diagnostics:
        warnings.append("diagnostics_json not provided; budget and run-level diagnostics omitted")

    diagnostic_lines = "\n".join(f"- {w}" for w in warnings)

    signal_framing = [
        "- Supported signal: consistent with a behavior-first routing signal under this toy pilot setup when appropriate_reliance_proxy > 0.",
        "- Unsupported signal: fails to support behavior-first routing benefit when commission_error_rate remains high with low override.",
        "- Inconclusive signal: inconclusive under current sample and task when condition gaps are small or unstable.",
    ]

    budget_note = "- Budget diagnostics: available in diagnostics JSON." if diagnostics else "- Budget diagnostics: TODO (not available in this run input)."

    lines = [
        "# Pilot Analysis Summary",
        "",
        _SIGNAL_NOTE,
        "",
        "## Session accounting",
        f"- N started: {started}",
        f"- N completed: {completed}",
        f"- N excluded-flagged: {excluded_flagged}",
        f"- Task family: {', '.join(task_families)}",
        "",
        "## Per-condition metric summary",
        *condition_lines,
        "",
        "## Diagnostic warnings",
        diagnostic_lines if diagnostic_lines else "- None",
        "",
        "## Signal framing",
        *signal_framing,
        "",
        "## Budget notes",
        budget_note,
    ]
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build concise markdown summary for pilot analysis")
    parser.add_argument("--trial-level-csv", required=True)
    parser.add_argument("--participant-summary-csv", required=True)
    parser.add_argument("--exclusions-csv", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--session-summary-csv")
    parser.add_argument("--diagnostics-json")
    args = parser.parse_args()

    trial_rows = load_rows(Path(args.trial_level_csv))
    participant_rows = load_rows(Path(args.participant_summary_csv))
    exclusion_rows = load_rows(Path(args.exclusions_csv))
    session_rows = load_rows(Path(args.session_summary_csv)) if args.session_summary_csv else []
    diagnostics = json.loads(Path(args.diagnostics_json).read_text(encoding="utf-8")) if args.diagnostics_json else {}

    report = build_report(trial_rows, participant_rows, exclusion_rows, session_rows, diagnostics)
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_md).write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
