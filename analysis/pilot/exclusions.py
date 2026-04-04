"""Explicit exclusion flag computation for pilot sessions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
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


def compute_exclusion_flags(
    trial_level_rows: list[dict[str, Any]],
    session_summary_rows: list[dict[str, Any]] | None = None,
    *,
    too_fast_median_ms: int = 350,
    missing_confidence_threshold: float = 0.2,
    repeated_same_response_threshold: float = 0.95,
) -> list[dict[str, Any]]:
    session_summary_rows = session_summary_rows or []
    by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trial_level_rows:
        by_session[str(row.get("session_id", ""))].append(row)

    session_lookup = {str(r.get("session_id", "")): r for r in session_summary_rows}

    flags: list[dict[str, Any]] = []
    for session_id, rows in by_session.items():
        participant_id = str(rows[0].get("participant_id", "")) if rows else ""
        rts = [_to_int(r.get("reaction_time_ms")) for r in rows]
        rts_valid = [rt for rt in rts if rt is not None]
        confidences = [_to_float(r.get("confidence")) for r in rows]
        missing_conf = sum(1 for c in confidences if c is None)

        responses = [str(r.get("followed_model", "")) + "|" + str(r.get("correct", "")) for r in rows]
        dominance = 0.0
        if responses:
            counts = Counter(responses)
            dominance = max(counts.values()) / len(responses)

        duplicate_trial_ids = len({r.get("trial_id") for r in rows}) != len(rows)
        missing_required = any(r.get("trial_id") in {None, ""} or r.get("stimulus_id") in {None, ""} for r in rows)

        session_meta = session_lookup.get(session_id, {})
        completed_status = str(session_meta.get("status", "")) in {"finalized", "completed"} if session_meta else False

        flags.append(
            {
                "session_id": session_id,
                "participant_id": participant_id,
                "n_trials": len(rows),
                "too_fast_responder": bool(rts_valid and median(rts_valid) < too_fast_median_ms),
                "missing_confidence_reports": (missing_conf / max(len(rows), 1)) > missing_confidence_threshold,
                "incomplete_session": (not completed_status) if session_meta else False,
                "repeated_same_response_pattern": (len(rows) >= 10) and (dominance >= repeated_same_response_threshold),
                "logging_corruption_flag": duplicate_trial_ids or missing_required,
                "dominant_response_pattern_share": round(dominance, 4),
            }
        )

    for session_id, meta in session_lookup.items():
        if session_id not in by_session:
            flags.append(
                {
                    "session_id": session_id,
                    "participant_id": str(meta.get("participant_id", "")),
                    "n_trials": 0,
                    "too_fast_responder": False,
                    "missing_confidence_reports": True,
                    "incomplete_session": str(meta.get("status", "")) not in {"finalized", "completed"},
                    "repeated_same_response_pattern": False,
                    "logging_corruption_flag": True,
                    "dominant_response_pattern_share": 0.0,
                }
            )

    return sorted(flags, key=lambda row: (str(row["participant_id"]), str(row["session_id"])))


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
    parser = argparse.ArgumentParser(description="Compute explicit exclusion flags for pilot sessions")
    parser.add_argument("--trial-level-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--session-summary-csv")
    args = parser.parse_args()

    trial_rows = load_rows(Path(args.trial_level_csv))
    session_rows = load_rows(Path(args.session_summary_csv)) if args.session_summary_csv else []
    flags = compute_exclusion_flags(trial_rows, session_rows)
    write_csv(flags, Path(args.output_csv))


if __name__ == "__main__":
    main()
