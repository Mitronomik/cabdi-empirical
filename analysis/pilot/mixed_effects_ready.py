"""Build mixed-effects-ready trial table for pilot analysis."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_mixed_effects_ready(
    trial_level_rows: list[dict[str, Any]],
    participant_summary_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    participant_summary_rows = participant_summary_rows or []
    summary_lookup = {
        (str(row.get("participant_id", "")), str(row.get("condition", ""))): row
        for row in participant_summary_rows
    }

    output: list[dict[str, Any]] = []
    for row in trial_level_rows:
        rt = float(row.get("reaction_time_ms") or 0.0)
        log_rt = math.log(rt) if rt > 0 else None
        summary = summary_lookup.get((str(row.get("participant_id", "")), str(row.get("condition", ""))), {})

        output.append(
            {
                "participant": row.get("participant_id", ""),
                "session_id": row.get("session_id", ""),
                "item": row.get("stimulus_id", ""),
                "condition": row.get("condition", ""),
                "block_id": row.get("block_id", ""),
                "trial_id": row.get("trial_id", ""),
                "order_index": row.get("order_index", ""),
                "trial_index": row.get("trial_index", ""),
                "correct": row.get("correct", 0),
                "model_wrong": row.get("model_wrong", 0),
                "followed_wrong_model": row.get("followed_wrong_model", 0),
                "correct_override": row.get("correct_override", 0),
                "reaction_time_ms": row.get("reaction_time_ms", 0),
                "log_rt": round(log_rt, 8) if log_rt is not None else None,
                "self_reported_burden": summary.get("self_reported_burden"),
                "trust_reliance_summary": summary.get("trust_reliance_summary"),
                "usefulness_summary": summary.get("usefulness_summary"),
            }
        )

    return output


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
    parser = argparse.ArgumentParser(description="Build mixed-effects-ready pilot table")
    parser.add_argument("--trial-level-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--participant-summary-csv")
    args = parser.parse_args()

    trial_rows = load_rows(Path(args.trial_level_csv))
    summary_rows = load_rows(Path(args.participant_summary_csv)) if args.participant_summary_csv else []
    output = build_mixed_effects_ready(trial_rows, summary_rows)
    write_csv(output, Path(args.output_csv))


if __name__ == "__main__":
    main()
