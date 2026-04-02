"""Researcher stimulus upload and validation service."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.participant_api.persistence.sqlite_store import SQLiteStore, dumps, loads
from packages.shared_types.pilot_types import StimulusItem


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StimulusService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def upload_stimulus_set(self, *, name: str, content: bytes, source_format: str) -> dict[str, Any]:
        fmt = source_format.lower().strip()
        if fmt not in {"jsonl", "csv"}:
            raise ValueError("source_format must be jsonl or csv")

        decoded = content.decode("utf-8")
        rows = self._parse_jsonl(decoded) if fmt == "jsonl" else self._parse_csv(decoded)
        if not rows:
            raise ValueError("Uploaded stimulus file is empty")

        seen_ids: set[str] = set()
        validated: list[StimulusItem] = []
        errors: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            try:
                item = StimulusItem.from_dict(row)
                if item.stimulus_id in seen_ids:
                    raise ValueError(f"Duplicate stimulus_id in upload: {item.stimulus_id}")
                seen_ids.add(item.stimulus_id)
                validated.append(item)
            except Exception as exc:  # noqa: BLE001 - explicit user-facing validation surface
                errors.append({"row": idx, "message": str(exc)})

        if errors:
            return {
                "ok": False,
                "errors": errors,
                "n_rows": len(rows),
                "preview": rows[:5],
            }

        stimulus_set_id = f"stim_{uuid4().hex[:10]}"
        task_families = {item.task_family for item in validated}
        if len(task_families) != 1:
            raise ValueError("Uploaded set must contain a single task_family")

        task_family = next(iter(task_families))
        serialized = [asdict(item) for item in validated]
        self.store.execute(
            """
            INSERT INTO researcher_stimulus_sets(
                stimulus_set_id, name, task_family, source_format, n_items, created_at, items_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stimulus_set_id,
                name,
                task_family,
                fmt,
                len(serialized),
                _now_iso(),
                dumps(serialized),
            ),
        )

        return {
            "ok": True,
            "stimulus_set_id": stimulus_set_id,
            "task_family": task_family,
            "n_items": len(serialized),
            "preview": serialized[:5],
            "errors": [],
        }

    def list_stimulus_sets(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            "SELECT stimulus_set_id, name, task_family, source_format, n_items, created_at FROM researcher_stimulus_sets ORDER BY created_at DESC",
            (),
        )
        return rows

    def get_stimulus_set(self, stimulus_set_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM researcher_stimulus_sets WHERE stimulus_set_id = ?", (stimulus_set_id,))
        if row is None:
            raise KeyError("stimulus_set not found")
        row["items"] = loads(row.pop("items_json"))
        return row

    def _parse_jsonl(self, content: str) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for line_no, raw_line in enumerate(content.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                parsed.append(json.loads(raw_line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {exc.msg}") from exc
        return parsed

    def _parse_csv(self, content: str) -> list[dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(content))
        rows: list[dict[str, Any]] = []
        for row_idx, row in enumerate(reader, start=2):
            try:
                payload = json.loads(row.get("payload", "{}"))
                eligible_raw = row.get("eligible_sets", "")
                if eligible_raw.startswith("["):
                    eligible_sets = json.loads(eligible_raw)
                else:
                    eligible_sets = [v.strip() for v in eligible_raw.split(";") if v.strip()]
                parsed = {
                    "stimulus_id": row.get("stimulus_id", ""),
                    "task_family": row.get("task_family", ""),
                    "content_type": row.get("content_type", ""),
                    "payload": payload,
                    "true_label": row.get("true_label", ""),
                    "difficulty_prior": row.get("difficulty_prior", ""),
                    "model_prediction": row.get("model_prediction", ""),
                    "model_confidence": row.get("model_confidence", ""),
                    "model_correct": self._parse_bool(row.get("model_correct", ""), "model_correct"),
                    "eligible_sets": eligible_sets,
                    "notes": row.get("notes") or None,
                }
                rows.append(parsed)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"CSV parsing error near row {row_idx}: {exc}") from exc
        return rows

    def _parse_bool(self, raw: Any, field: str) -> bool:
        value = str(raw).strip().lower()
        if value in {"1", "true", "yes"}:
            return True
        if value in {"0", "false", "no"}:
            return False
        raise ValueError(f"{field} must be a boolean-like value")
