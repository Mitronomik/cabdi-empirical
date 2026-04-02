"""Derive trial-level observable-anchor metrics for pilot analysis."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


_REQUIRED_COLUMNS = {
    "participant_id",
    "session_id",
    "condition",
    "stimulus_id",
    "task_family",
    "human_response",
    "correct_or_not",
    "model_correct_or_not",
    "accepted_model_advice",
    "overrode_model",
    "reaction_time_ms",
    "self_confidence",
    "verification_completed",
    "reason_clicked",
    "evidence_opened",
}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def load_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows


def parse_event_log(event_log_path: Path | None) -> dict[str, dict[str, Any]]:
    if event_log_path is None or not event_log_path.exists():
        return {}
    by_trial: dict[str, dict[str, Any]] = {}
    with event_log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            trial_id = str(payload.get("trial_id", ""))
            if not trial_id:
                continue
            block_id = str(payload.get("block_id", ""))
            record = by_trial.setdefault(trial_id, {"block_id": block_id, "event_count": 0})
            record["event_count"] = int(record["event_count"]) + 1
            if block_id:
                record["block_id"] = block_id
    return by_trial


def _extract_trial_order(trial_id: str) -> int | None:
    if "_t" not in trial_id:
        return None
    tail = trial_id.rsplit("_t", 1)[-1]
    if tail.isdigit():
        return int(tail)
    return None


def derive_trial_level_rows(
    trial_summary_rows: list[dict[str, Any]],
    event_trial_map: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    event_trial_map = event_trial_map or {}
    warnings: list[str] = []
    output: list[dict[str, Any]] = []
    missing_cols = _REQUIRED_COLUMNS - set(trial_summary_rows[0].keys()) if trial_summary_rows else set()
    if missing_cols:
        warnings.append(f"missing_required_columns:{','.join(sorted(missing_cols))}")

    session_trial_counter: dict[tuple[str, str], int] = defaultdict(int)

    for idx, row in enumerate(trial_summary_rows, start=1):
        trial_id = str(row.get("trial_id") or row.get("_trial_id") or f"unknown_t{idx}")
        session_id = str(row.get("session_id", ""))
        key = (session_id, trial_id)
        session_trial_counter[key] += 1

        meta = event_trial_map.get(trial_id, {})
        reaction_time = _to_int(row.get("reaction_time_ms"))
        if reaction_time is None:
            warnings.append(f"missing_rt:row_{idx}")
            reaction_time = 0

        correct = _to_bool(row.get("correct_or_not"))
        model_wrong = not _to_bool(row.get("model_correct_or_not"))
        followed_model = _to_bool(row.get("accepted_model_advice"))
        overrode_model = _to_bool(row.get("overrode_model"))
        followed_wrong_model = model_wrong and followed_model
        correct_override = model_wrong and overrode_model and correct

        derived = {
            "participant_id": row.get("participant_id", ""),
            "session_id": session_id,
            "experiment_id": row.get("experiment_id", ""),
            "condition": row.get("condition", ""),
            "task_family": row.get("task_family", ""),
            "block_id": row.get("block_id") or meta.get("block_id", ""),
            "trial_id": trial_id,
            "trial_index": _extract_trial_order(trial_id),
            "stimulus_id": row.get("stimulus_id", ""),
            "correct": int(correct),
            "incorrect": int(not correct),
            "utility_accuracy": int(correct),
            "model_wrong": int(model_wrong),
            "followed_model": int(followed_model),
            "followed_wrong_model": int(followed_wrong_model),
            "correct_override": int(correct_override),
            "reaction_time_ms": reaction_time,
            "confidence": _to_int(row.get("self_confidence")),
            "verification_completed": int(_to_bool(row.get("verification_completed"))),
            "verification_required": int(_to_bool(row.get("verification_required"))),
            "verification_burden": int(_to_bool(row.get("verification_completed"))),
            "reason_clicked": int(_to_bool(row.get("reason_clicked"))),
            "reason_click_rate": int(_to_bool(row.get("reason_clicked"))),
            "evidence_opened": int(_to_bool(row.get("evidence_opened"))),
            "evidence_open_rate": int(_to_bool(row.get("evidence_opened"))),
            "switch_burden_proxy": int(
                _to_bool(row.get("reason_clicked"))
                or _to_bool(row.get("evidence_opened"))
                or _to_bool(row.get("verification_completed"))
            ),
            "order_index": row.get("order_index") or row.get("block_index") or "",
        }
        output.append(derived)

    duplicates = [k for k, v in session_trial_counter.items() if v > 1]
    if duplicates:
        warnings.append(f"duplicate_trial_ids:{len(duplicates)}")
    return output, warnings


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive trial-level pilot metrics from trial summaries")
    parser.add_argument("--trial-summary-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--event-log-jsonl", required=False)
    parser.add_argument("--warnings-json", required=False)
    args = parser.parse_args()

    trial_rows = load_csv_rows(Path(args.trial_summary_csv))
    event_map = parse_event_log(Path(args.event_log_jsonl)) if args.event_log_jsonl else {}
    derived_rows, warnings = derive_trial_level_rows(trial_rows, event_map)
    write_csv(derived_rows, Path(args.output_csv))

    if args.warnings_json:
        Path(args.warnings_json).write_text(json.dumps({"warnings": warnings}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
