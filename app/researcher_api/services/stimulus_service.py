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

_ALLOWED_TASK_FAMILIES = {"scam_detection", "scam_not_scam"}
_ALLOWED_CONTENT_TYPES = {"text", "image", "vignette"}
_ALLOWED_DIFFICULTY = {"low", "medium", "high"}
_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_PAYLOAD_SCHEMA_VERSION = "stimulus_payload.v1"
_PREVIEW_ROWS_LIMIT = 5

_TASK_LABEL_SPACE = {
    "scam_detection": {"scam", "not_scam"},
    "scam_not_scam": {"scam", "not_scam"},
}


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
        canonical_items: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            row_errors, row_warnings, canonical = self._canonicalize_row(row)
            if canonical:
                stimulus_id = canonical["stimulus_id"]
                if stimulus_id in seen_ids:
                    row_errors.append({"severity": "release_blocker", "code": "duplicate_stimulus_id", "message": f"Duplicate stimulus_id in upload: {stimulus_id}"})
                seen_ids.add(stimulus_id)

            if row_errors:
                errors.extend({"row": idx, **error} for error in row_errors)
            warnings.extend({"row": idx, **warning} for warning in row_warnings)
            if canonical and not row_errors:
                canonical_items.append(canonical)

        task_families = {item["task_family"] for item in canonical_items}
        if len(task_families) > 1:
            errors.append(
                {
                    "row": None,
                    "severity": "release_blocker",
                    "code": "mixed_task_family",
                    "message": "Uploaded set must contain a single task_family",
                }
            )

        task_family = next(iter(task_families)) if task_families else None
        preview_rows = canonical_items[:_PREVIEW_ROWS_LIMIT]
        n_items = len(canonical_items)

        validation_status = "invalid" if errors else ("warning_only" if warnings else "valid")
        is_valid = validation_status in {"valid", "warning_only"}
        response_stimulus_set_id: str | None = None

        if is_valid and task_family:
            response_stimulus_set_id = f"stim_{uuid4().hex[:10]}"
            serialized = [StimulusItem.from_dict(item).to_dict() for item in canonical_items]
            self.store.execute(
                """
                INSERT INTO researcher_stimulus_sets(
                    stimulus_set_id, name, task_family, source_format, n_items, created_at, items_json,
                    validation_status, payload_schema_version, warnings_json, errors_json, preview_rows_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_stimulus_set_id,
                    name,
                    task_family,
                    fmt,
                    len(serialized),
                    _now_iso(),
                    dumps(serialized),
                    validation_status,
                    _PAYLOAD_SCHEMA_VERSION,
                    dumps(warnings),
                    dumps([]),
                    dumps(preview_rows),
                ),
            )

        return {
            "ok": is_valid,
            "success": is_valid,
            "stimulus_set_id": response_stimulus_set_id,
            "n_items": n_items,
            "task_family": task_family,
            "validation_status": validation_status,
            "warnings": warnings,
            "errors": errors,
            "preview_rows": preview_rows,
            "payload_schema_version": _PAYLOAD_SCHEMA_VERSION,
            "source_format": fmt,
            "n_rows": len(rows),
            "renderer_compatible": is_valid,
            "run_compatible": is_valid,
        }

    def list_stimulus_sets(self) -> list[dict[str, Any]]:
        rows = self.store.fetchall(
            """
            SELECT stimulus_set_id, name, task_family, source_format, n_items, created_at,
                   validation_status, payload_schema_version, warnings_json, errors_json, preview_rows_json
            FROM researcher_stimulus_sets
            ORDER BY created_at DESC
            """,
            (),
        )
        return [self._inflate_metadata(row) for row in rows]

    def get_stimulus_set(self, stimulus_set_id: str) -> dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM researcher_stimulus_sets WHERE stimulus_set_id = ?", (stimulus_set_id,))
        if row is None:
            raise KeyError("stimulus_set not found")
        row["items"] = loads(row.pop("items_json"))
        return self._inflate_metadata(row)

    def _inflate_metadata(self, row: dict[str, Any]) -> dict[str, Any]:
        inflated = dict(row)
        inflated["warnings"] = loads(inflated.pop("warnings_json", "[]"))
        inflated["errors"] = loads(inflated.pop("errors_json", "[]"))
        inflated["preview_rows"] = loads(inflated.pop("preview_rows_json", "[]"))
        return inflated

    def _canonicalize_row(self, row: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any] | None]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        stimulus_id = str(row.get("stimulus_id", "")).strip()
        task_family = str(row.get("task_family", "")).strip()
        content_type = str(row.get("content_type", "")).strip()
        true_label = str(row.get("true_label", "")).strip()
        difficulty_prior = str(row.get("difficulty_prior", "")).strip()
        model_prediction = str(row.get("model_prediction", "")).strip()
        model_confidence = str(row.get("model_confidence", "")).strip()
        notes_raw = row.get("notes")

        payload_in = row.get("payload")
        payload, payload_errors, payload_warnings = self._canonicalize_payload(payload_in)
        errors.extend(payload_errors)
        warnings.extend(payload_warnings)

        if not stimulus_id:
            errors.append(self._err("missing_required", "stimulus_id must be non-empty"))
        if task_family not in _ALLOWED_TASK_FAMILIES:
            errors.append(self._err("invalid_task_family", "task_family must be one of supported task families"))
        if content_type not in _ALLOWED_CONTENT_TYPES:
            errors.append(self._err("invalid_content_type", "content_type must be compatible with supported renderer"))
        if not true_label:
            errors.append(self._err("missing_required", "true_label must be non-empty"))
        if difficulty_prior not in _ALLOWED_DIFFICULTY:
            errors.append(self._err("invalid_difficulty_prior", "difficulty_prior must be low|medium|high"))
        if not model_prediction:
            errors.append(self._err("missing_required", "model_prediction must be non-empty"))
        if model_confidence not in _ALLOWED_CONFIDENCE:
            errors.append(self._err("invalid_model_confidence", "model_confidence must be low|medium|high"))

        label_space = _TASK_LABEL_SPACE.get(task_family, set())
        if label_space:
            if true_label and true_label not in label_space:
                errors.append(self._err("invalid_true_label", "true_label is incompatible with task_family label space"))
            if model_prediction and model_prediction not in label_space:
                errors.append(
                    self._err("invalid_model_prediction", "model_prediction is incompatible with task_family label space")
                )

        model_correct_raw = row.get("model_correct")
        try:
            model_correct = self._coerce_bool(model_correct_raw)
        except ValueError:
            if model_correct_raw in {None, ""} and true_label and model_prediction and true_label == model_prediction:
                model_correct = True
                warnings.append(self._warn("derived_model_correct", "model_correct was derived from labels"))
            elif model_correct_raw in {None, ""} and true_label and model_prediction and true_label != model_prediction:
                model_correct = False
                warnings.append(self._warn("derived_model_correct", "model_correct was derived from labels"))
            else:
                errors.append(self._err("invalid_model_correct", "model_correct must be bool or derivable from labels"))
                model_correct = False

        if model_prediction and true_label and bool(model_correct) != (model_prediction == true_label):
            errors.append(self._err("inconsistent_model_correct", "model_correct must be consistent with model_prediction and true_label"))

        eligible_sets, eligible_err = self._parse_eligible_sets(row.get("eligible_sets"))
        if eligible_err:
            errors.append(self._err("invalid_eligible_sets", eligible_err))

        if errors:
            return errors, warnings, None

        canonical = {
            "stimulus_id": stimulus_id,
            "task_family": task_family,
            "content_type": content_type,
            "payload": payload,
            "true_label": true_label,
            "difficulty_prior": difficulty_prior,
            "model_prediction": model_prediction,
            "model_confidence": model_confidence,
            "model_correct": bool(model_correct),
            "eligible_sets": eligible_sets,
            "notes": str(notes_raw).strip() if notes_raw is not None and str(notes_raw).strip() else None,
        }
        return errors, warnings, canonical

    def _canonicalize_payload(self, payload: Any) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if not isinstance(payload, dict):
            return {}, [self._err("invalid_payload", "payload must be an object")], warnings

        title = str(payload.get("title", "")).strip()
        body = str(payload.get("body", "")).strip()

        legacy_keys = ["message", "scenario", "text", "prompt"]
        if not body:
            legacy_values = [str(payload.get(key, "")).strip() for key in legacy_keys]
            legacy_values = [value for value in legacy_values if value]
            if len(legacy_values) == 1:
                body = legacy_values[0]
                warnings.append(self._warn("legacy_payload_normalized", "legacy payload field was normalized into payload.body"))
            elif len(legacy_values) > 1:
                errors.append(
                    self._err(
                        "ambiguous_legacy_payload",
                        "payload.body missing and multiple legacy body fields present",
                    )
                )

        if not title:
            title = str(payload.get("channel", "")).strip() or "Untitled stimulus"
            warnings.append(self._warn("title_defaulted", "payload.title was missing and defaulted"))

        if not title:
            errors.append(self._err("missing_payload_title", "payload.title must be non-empty"))
        if not body:
            errors.append(self._err("missing_payload_body", "payload.body must be non-empty or resolvable from legacy keys"))

        normalized = {"title": title, "body": body}
        response_options = payload.get("response_options")
        if isinstance(response_options, list) and all(isinstance(opt, str) and opt.strip() for opt in response_options):
            normalized["response_options"] = [opt.strip() for opt in response_options]

        for passthrough_key in ["rationale", "evidence", "channel"]:
            value = payload.get(passthrough_key)
            if isinstance(value, str) and value.strip():
                normalized[passthrough_key] = value.strip()

        return normalized, errors, warnings

    def _parse_jsonl(self, content: str) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for line_no, raw_line in enumerate(content.splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                loaded = json.loads(raw_line)
                if not isinstance(loaded, dict):
                    raise ValueError("line must contain a JSON object")
                parsed.append(loaded)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
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
                    "model_correct": row.get("model_correct", ""),
                    "eligible_sets": eligible_sets,
                    "notes": row.get("notes") or None,
                }
                rows.append(parsed)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"CSV parsing error near row {row_idx}: {exc}") from exc
        return rows

    def _coerce_bool(self, raw: Any) -> bool:
        if isinstance(raw, bool):
            return raw
        value = str(raw).strip().lower()
        if value in {"1", "true", "yes"}:
            return True
        if value in {"0", "false", "no"}:
            return False
        raise ValueError("value is not boolean-like")

    def _parse_eligible_sets(self, raw: Any) -> tuple[list[str], str | None]:
        if raw is None:
            return [], None
        if not isinstance(raw, list):
            return [], "eligible_sets must be an array"
        values = [str(v).strip() for v in raw if str(v).strip()]
        if len(values) != len(raw):
            return [], "eligible_sets must contain non-empty strings"
        return values, None

    def _err(self, code: str, message: str) -> dict[str, str]:
        return {"severity": "release_blocker", "code": code, "message": message}

    def _warn(self, code: str, message: str) -> dict[str, str]:
        return {"severity": "warning", "code": code, "message": message}
