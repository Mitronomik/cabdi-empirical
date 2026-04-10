#!/usr/bin/env python3
"""Create timestamped pilot backups with retention for VPS-style operations."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from app.participant_api.persistence.backup_restore import backup_database

BACKUP_PREFIX = "pilot_backup_"
BACKUP_SUFFIX = ".json"
BACKUP_NAME_PATTERN = re.compile(r"^pilot_backup_(\d{8}T\d{6}Z)\.json$")


def _resolve_db_target(db_target: str | None) -> str:
    resolved = (db_target or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH") or "").strip()
    if not resolved:
        raise RuntimeError("No DB target resolved. Provide --db-target or set PILOT_DB_URL/PILOT_DB_PATH.")
    return resolved


def build_backup_name(*, timestamp_utc: str) -> str:
    return f"{BACKUP_PREFIX}{timestamp_utc}{BACKUP_SUFFIX}"


def list_backups(backup_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if BACKUP_NAME_PATTERN.match(path.name):
            candidates.append(path)
    return sorted(candidates, key=lambda p: p.name)


def apply_retention(*, backup_dir: Path, retain_count: int) -> list[str]:
    if retain_count <= 0:
        raise RuntimeError("--retain-count must be >= 1")
    backups = list_backups(backup_dir)
    if len(backups) <= retain_count:
        return []

    to_delete = backups[: len(backups) - retain_count]
    deleted: list[str] = []
    for path in to_delete:
        path.unlink(missing_ok=True)
        deleted.append(str(path))
    return deleted


def run_rotation(*, db_target: str, backup_dir: Path, timestamp_utc: str, retain_count: int) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    output_path = backup_dir / build_backup_name(timestamp_utc=timestamp_utc)
    backup_result = backup_database(db_target=db_target, output_path=str(output_path))
    deleted_paths = apply_retention(backup_dir=backup_dir, retain_count=retain_count)
    retained_after = [str(path) for path in list_backups(backup_dir)]
    return {
        "backup_path": str(output_path),
        "deleted_paths": deleted_paths,
        "retained_count": len(retained_after),
        "retained_paths": retained_after,
        "backup_result": backup_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create timestamped pilot backup and apply retention policy.")
    parser.add_argument("--db-target", default=None, help="DB target (postgres URL or sqlite path).")
    parser.add_argument("--backup-dir", required=True, help="Directory for timestamped backup artifacts.")
    parser.add_argument(
        "--timestamp-utc",
        required=True,
        help="UTC timestamp token in YYYYMMDDTHHMMSSZ format (recommended: $(date -u +%Y%m%dT%H%M%SZ)).",
    )
    parser.add_argument("--retain-count", type=int, default=14, help="How many backups to keep (oldest are deleted).")
    args = parser.parse_args()

    if not re.match(r"^\d{8}T\d{6}Z$", args.timestamp_utc):
        raise RuntimeError("--timestamp-utc must match YYYYMMDDTHHMMSSZ.")

    result = run_rotation(
        db_target=_resolve_db_target(args.db_target),
        backup_dir=Path(args.backup_dir),
        timestamp_utc=args.timestamp_utc,
        retain_count=args.retain_count,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"backup rotation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
