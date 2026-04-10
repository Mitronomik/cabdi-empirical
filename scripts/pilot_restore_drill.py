#!/usr/bin/env python3
"""Run a repository-owned backup/restore verification drill for VPS staging."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from app.participant_api.persistence.backup_restore import backup_database, restore_database
from scripts.pilot_backup_rotate import build_backup_name


def _resolve_db_target(db_target: str | None) -> str:
    resolved = (db_target or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH") or "").strip()
    if not resolved:
        raise RuntimeError("No DB target resolved. Provide --db-target or set PILOT_DB_URL/PILOT_DB_PATH.")
    return resolved


def run_restore_drill(*, db_target: str, backup_dir: Path, timestamp_utc: str) -> dict[str, Any]:
    if not re.match(r"^\d{8}T\d{6}Z$", timestamp_utc):
        raise RuntimeError("timestamp_utc must match YYYYMMDDTHHMMSSZ.")

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / build_backup_name(timestamp_utc=timestamp_utc)
    baseline = backup_database(db_target=db_target, output_path=str(backup_path))
    restored = restore_database(db_target=db_target, backup_path=str(backup_path), confirm_destructive=True)

    baseline_counts = baseline.get("row_counts", {})
    restored_counts = restored.get("restored_counts", {})
    verification_ok = baseline_counts == restored_counts
    verification_detail = "row-count parity preserved after restore" if verification_ok else "row-count mismatch after restore"

    return {
        "backup_path": str(backup_path),
        "baseline_row_counts": baseline_counts,
        "restored_counts": restored_counts,
        "verification_ok": verification_ok,
        "verification_detail": verification_detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run destructive backup/restore drill with verification.")
    parser.add_argument("--db-target", default=None, help="DB target (postgres URL or sqlite path).")
    parser.add_argument("--backup-dir", required=True, help="Directory for drill backup artifact.")
    parser.add_argument(
        "--timestamp-utc",
        required=True,
        help="UTC timestamp token in YYYYMMDDTHHMMSSZ format (recommended: $(date -u +%Y%m%dT%H%M%SZ)).",
    )
    parser.add_argument("--report-out", default=None, help="Optional report JSON path.")
    args = parser.parse_args()

    report = run_restore_drill(
        db_target=_resolve_db_target(args.db_target),
        backup_dir=Path(args.backup_dir),
        timestamp_utc=args.timestamp_utc,
    )
    if args.report_out:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))

    if not report["verification_ok"]:
        raise RuntimeError(report["verification_detail"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"restore drill failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
