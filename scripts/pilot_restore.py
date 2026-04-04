#!/usr/bin/env python3
"""Restore repository-owned pilot data backups."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.participant_api.persistence.backup_restore import BackupRestoreError, restore_database


def _resolve_db_target(db_target: str | None) -> str:
    resolved = (db_target or os.getenv("PILOT_DB_URL") or os.getenv("PILOT_DB_PATH") or "pilot/sessions/pilot_sessions.sqlite3").strip()
    if not resolved:
        raise RuntimeError("No DB target resolved. Provide --db-target or set PILOT_DB_URL/PILOT_DB_PATH.")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore CABDI pilot backup artifact (destructive).")
    parser.add_argument("--db-target", default=None, help="DB target (postgres URL or sqlite path).")
    parser.add_argument("--backup", required=True, help="Backup file produced by scripts/pilot_backup.py")
    parser.add_argument(
        "--confirm-destructive",
        action="store_true",
        help="Required flag. Restore replaces current pilot tables.",
    )
    args = parser.parse_args()

    result = restore_database(
        db_target=_resolve_db_target(args.db_target),
        backup_path=args.backup,
        confirm_destructive=args.confirm_destructive,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackupRestoreError as exc:
        print(f"restore refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"restore failed: {exc}", file=sys.stderr)
        raise SystemExit(3)
