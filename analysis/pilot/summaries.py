"""Participant/session-level summaries for pilot analysis outputs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _questionnaire_means(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    by_session: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        session_id = str(row.get("session_id", ""))
        for key in ("burden", "trust", "usefulness"):
            val = _to_float(row.get(key))
            if val is not None:
                by_session[session_id][key].append(val)

    out: dict[str, dict[str, float | None]] = {}
    for session_id, metrics in by_session.items():
        out[session_id] = {
            "self_reported_burden": mean(metrics.get("burden", [])) if metrics.get("burden") else None,
            "trust_reliance_summary": mean(metrics.get("trust", [])) if metrics.get("trust") else None,
            "usefulness_summary": mean(metrics.get("usefulness", [])) if metrics.get("usefulness") else None,
        }
    return out


def build_participant_summary(
    trial_level_rows: list[dict[str, Any]],
    exclusions_rows: list[dict[str, Any]],
    questionnaire_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    questionnaire_rows = questionnaire_rows or []
    exclusion_by_session = {str(r.get("session_id", "")): r for r in exclusions_rows}
    q_by_session = _questionnaire_means(questionnaire_rows)

    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in trial_level_rows:
        key = (str(row.get("participant_id", "")), str(row.get("condition", "")))
        by_group[key].append(row)

    summaries: list[dict[str, Any]] = []
    for (participant_id, condition), rows in sorted(by_group.items()):
        session_id = str(rows[0].get("session_id", ""))
        n_trials = len(rows)
        model_wrong_rows = [r for r in rows if int(r.get("model_wrong", 0)) == 1]
        model_correct_rows = [r for r in rows if int(r.get("model_wrong", 0)) == 0]

        follow_when_correct = mean(int(r.get("followed_model", 0)) for r in model_correct_rows) if model_correct_rows else 0.0
        follow_when_wrong = mean(int(r.get("followed_model", 0)) for r in model_wrong_rows) if model_wrong_rows else 0.0

        q_values = q_by_session.get(session_id, {})
        exclusion = exclusion_by_session.get(session_id, {})

        summaries.append(
            {
                "participant_id": participant_id,
                "session_id": session_id,
                "condition": condition,
                "n_trials": n_trials,
                "utility_accuracy": round(mean(int(r.get("utility_accuracy", 0)) for r in rows), 6),
                "commission_error_rate": round(mean(int(r.get("followed_wrong_model", 0)) for r in rows), 6),
                "correct_override_rate": round(
                    mean(int(r.get("correct_override", 0)) for r in model_wrong_rows) if model_wrong_rows else 0.0,
                    6,
                ),
                "appropriate_reliance_proxy": round(follow_when_correct - follow_when_wrong, 6),
                "mean_rt": round(mean(_to_int(r.get("reaction_time_ms")) or 0 for r in rows), 3),
                "verification_burden": round(mean(int(r.get("verification_burden", 0)) for r in rows), 6),
                "reason_click_rate": round(mean(int(r.get("reason_click_rate", 0)) for r in rows), 6),
                "evidence_open_rate": round(mean(int(r.get("evidence_open_rate", 0)) for r in rows), 6),
                "switch_burden_proxy": round(mean(int(r.get("switch_burden_proxy", 0)) for r in rows), 6),
                "self_reported_burden": q_values.get("self_reported_burden"),
                "trust_reliance_summary": q_values.get("trust_reliance_summary"),
                "usefulness_summary": q_values.get("usefulness_summary"),
                "excluded_flagged": bool(
                    exclusion.get("too_fast_responder")
                    or exclusion.get("missing_confidence_reports")
                    or exclusion.get("incomplete_session")
                    or exclusion.get("repeated_same_response_pattern")
                    or exclusion.get("logging_corruption_flag")
                ),
            }
        )

    return summaries


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build participant-level summary for pilot analysis")
    parser.add_argument("--trial-level-csv", required=True)
    parser.add_argument("--exclusions-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--block-questionnaire-csv")
    args = parser.parse_args()

    trial_rows = load_rows(Path(args.trial_level_csv))
    exclusion_rows = load_rows(Path(args.exclusions_csv))
    questionnaire_rows = load_rows(Path(args.block_questionnaire_csv)) if args.block_questionnaire_csv else []

    summary_rows = build_participant_summary(trial_rows, exclusion_rows, questionnaire_rows)
    write_csv(summary_rows, Path(args.output_csv))


if __name__ == "__main__":
    main()
