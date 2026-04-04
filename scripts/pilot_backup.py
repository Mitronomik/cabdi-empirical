#!/usr/bin/env python3
"""Create repository-owned pilot data backups."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.participant_api.persistence.backup_restore import backup_database


def _resolve_db_target(db_target: str | None) -> str:
    resolved = (db_target or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH") or "pilot/sessions/pilot_sessions.sqlite3").strip()
    if not resolved:
        raise RuntimeError("No DB target resolved. Provide --db-target or set PILOT_DB_URL/PILOT_DB_PATH.")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Create CABDI pilot backup artifact (JSON format).")
    parser.add_argument("--db-target", default=None, help="DB target (postgres URL or sqlite path).")
    parser.add_argument("--output", required=True, help="Output backup file path.")
    args = parser.parse_args()

    result = backup_database(db_target=_resolve_db_target(args.db_target), output_path=args.output)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"backup failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
