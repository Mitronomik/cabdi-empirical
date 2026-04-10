"""Run-level researcher exports built from existing session artifacts."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analysis.pilot.derive_metrics import derive_trial_level_rows
from analysis.pilot.exclusions import compute_exclusion_flags
from analysis.pilot.mixed_effects_ready import build_mixed_effects_ready
from analysis.pilot.report_builder import build_report
from analysis.pilot.summaries import build_participant_summary
from app.participant_api.persistence.json_codec import loads
from app.participant_api.persistence.store_protocol import PilotStore
from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.run_data_service import RunDataService


@dataclass(frozen=True)
class ExportArtifact:
    artifact_type: str
    category: str
    data_layer: str
    filename: str
    media_type: str
    relative_path: str
    size_bytes: int
    available: bool


class AdminExportService:
    MANIFEST_VERSION = "pilot_export_manifest.v1"

    def __init__(self, store: PilotStore, export_root: str | Path = "artifacts/pilot_exports") -> None:
        self.store = store
        self.run_data_service = RunDataService(store)
        self.diagnostics_service = DiagnosticsService(store)
        self.export_root = Path(export_root)

    def export_run(self, run_id: str) -> dict[str, Any]:
        run_data = self.run_data_service.load_run_scoped_data(run_id)
        session_payload = run_data.session_payload
        session_ids = run_data.session_ids
        export_dir = self._run_export_dir(run_id)
        generated_at = datetime.now(timezone.utc).isoformat()

        if not session_ids:
            artifacts = self._persist_run_artifacts(
                run_id=run_id,
                generated_at=generated_at,
                warnings=["No sessions linked to this run yet"],
                source_data={
                    "session_rows": 0,
                    "trial_rows": 0,
                    "trial_summary_rows": 0,
                    "event_rows": 0,
                    "questionnaire_rows": 0,
                },
                payloads={
                    "raw_event_log_jsonl": "",
                    "trial_summary_csv": "",
                    "block_questionnaire_csv": "",
                    "session_summary_csv": "",
                    "session_summary_json": "[]\n",
                    "trial_level_csv": "",
                    "participant_summary_csv": "",
                    "mixed_effects_ready_csv": "",
                    "pilot_summary_md": "",
                },
            )
            return self._export_response({
                "run_id": run_id,
                "export_state": "empty",
                "generated_at": generated_at,
                "message": "No sessions for this run yet. Start participant sessions before exporting.",
                "session_summary_json": [],
                "available_outputs": {
                    "raw_event_log_jsonl": False,
                    "trial_summary_csv": False,
                    "block_questionnaire_csv": False,
                    "session_summary_csv": False,
                    "trial_level_csv": False,
                    "participant_summary_csv": False,
                    "mixed_effects_ready_csv": False,
                    "pilot_summary_md": False,
                },
                "artifacts": artifacts,
                "artifact_root": str(export_dir),
                "warnings": ["No sessions linked to this run yet"],
            })

        raw_event_log_jsonl = "\n".join(
            json.dumps(
                {
                    "event_id": row["event_id"],
                    "session_id": row["session_id"],
                    "block_id": row["block_id"],
                    "trial_id": row["trial_id"],
                    "timestamp": row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": loads(row["payload_json"]),
                },
                sort_keys=True,
            )
            for row in run_data.event_rows
        )

        trial_summary_csv = _to_csv(run_data.trial_summary_rows)

        session_summary_rows = []
        for row in session_payload["sessions"]:
            session_row = dict(row)
            session_row["run_id"] = run_id
            session_summary_rows.append(session_row)

        warnings: list[str] = []
        trial_level_rows: list[dict[str, Any]] = []
        participant_rows: list[dict[str, Any]] = []
        mixed_rows: list[dict[str, Any]] = []
        report_md = ""
        diagnostics = self.diagnostics_service.get_run_diagnostics(run_id)
        if run_data.trial_summary_rows:
            trial_level_rows, derive_warnings = derive_trial_level_rows(run_data.trial_summary_rows)
            warnings.extend(derive_warnings)
            exclusion_rows = compute_exclusion_flags(trial_level_rows, session_summary_rows)
            participant_rows = build_participant_summary(trial_level_rows, exclusion_rows, run_data.questionnaire_rows)
            mixed_rows = build_mixed_effects_ready(trial_level_rows, participant_rows)
            report_md = build_report(
                trial_level_rows,
                participant_rows,
                exclusion_rows,
                session_summary_rows,
                diagnostics,
            )
        else:
            warnings.append("No trial summaries available; derived analysis-ready outputs are unavailable")

        payloads = {
            "raw_event_log_jsonl": raw_event_log_jsonl,
            "trial_summary_csv": trial_summary_csv,
            "block_questionnaire_csv": _to_csv(run_data.questionnaire_rows),
            "session_summary_csv": _to_csv(session_summary_rows),
            "session_summary_json": json.dumps(session_summary_rows, indent=2, sort_keys=True),
            "trial_level_csv": _to_csv(trial_level_rows),
            "participant_summary_csv": _to_csv(participant_rows),
            "mixed_effects_ready_csv": _to_csv(mixed_rows),
            "pilot_summary_md": report_md,
        }
        artifacts = self._persist_run_artifacts(
            run_id=run_id,
            generated_at=generated_at,
            warnings=warnings,
            source_data={
                "session_rows": len(run_data.session_rows),
                "trial_rows": len(run_data.trial_rows),
                "trial_summary_rows": len(run_data.trial_summary_rows),
                "event_rows": len(run_data.event_rows),
                "questionnaire_rows": len(run_data.questionnaire_rows),
            },
            payloads=payloads,
        )

        return self._export_response({
            "run_id": run_id,
            "export_state": "available",
            "generated_at": generated_at,
            "message": "Run exports are available.",
            "session_summary_json": session_summary_rows,
            "available_outputs": {
                "raw_event_log_jsonl": bool(raw_event_log_jsonl),
                "trial_summary_csv": bool(trial_summary_csv),
                "block_questionnaire_csv": bool(run_data.questionnaire_rows),
                "session_summary_csv": bool(session_summary_rows),
                "trial_level_csv": bool(trial_level_rows),
                "participant_summary_csv": bool(participant_rows),
                "mixed_effects_ready_csv": bool(mixed_rows),
                "pilot_summary_md": bool(report_md),
            },
            "artifacts": artifacts,
            "artifact_root": str(export_dir),
            "warnings": warnings,
        })

    def get_artifact_path(self, run_id: str, artifact_type: str) -> tuple[Path, str]:
        manifest_path = self._run_export_dir(run_id) / "manifest.json"
        if not manifest_path.exists():
            raise KeyError("export artifacts unavailable; generate run export first")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = {item["artifact_type"]: item for item in manifest.get("artifacts", [])}
        artifact = artifacts.get(artifact_type)
        if artifact is None:
            raise KeyError(f"artifact not found: {artifact_type}")
        path = self.export_root / artifact["relative_path"]
        if not path.exists():
            raise KeyError(f"artifact file missing: {artifact_type}")
        return path, artifact.get("media_type", "application/octet-stream")

    def _export_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact_types = {item["artifact_type"]: item for item in payload.get("artifacts", [])}
        payload["artifact_policy"] = {"mode": "replace_current", "notes": "Re-generating exports overwrites run/current artifacts."}
        payload["source_of_truth"] = {
            "persisted_tables": [
                "participant_sessions",
                "session_trials",
                "trial_summary_logs",
                "trial_event_logs",
                "block_questionnaires",
                "pilot_runs",
            ],
            "derived_artifacts_root": str(self.export_root),
        }
        payload["artifact_layers"] = {
            "source_of_truth_extracts": sorted(
                item["artifact_type"] for item in artifact_types.values() if item["data_layer"] == "source_of_truth_extract"
            ),
            "derived_analysis_artifacts": sorted(
                item["artifact_type"] for item in artifact_types.values() if item["data_layer"] == "derived_analysis_artifact"
            ),
        }
        payload["manifest_version"] = self.MANIFEST_VERSION
        payload["run_scope"] = {
            "scope_level": "run",
            "run_id": payload.get("run_id"),
            "artifact_root": payload.get("artifact_root"),
        }
        payload["interpretation_semantics"] = {
            "claim_layer": "behavior_first_only",
            "supports": [
                "run-level and cohort-level behavior-first evidence statements",
                "confirmatory/narrowing analysis readiness assessment",
            ],
            "does_not_support": [
                "physiology-grounded interpretation",
                "participant psych/cognition inference",
                "whole-framework real-world validation claims",
            ],
        }
        return payload

    def _run_export_dir(self, run_id: str) -> Path:
        return self.export_root / run_id / "current"

    def _persist_run_artifacts(
        self,
        run_id: str,
        generated_at: str,
        warnings: list[str],
        source_data: dict[str, int],
        payloads: dict[str, str],
    ) -> list[dict[str, Any]]:
        export_dir = self._run_export_dir(run_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[ExportArtifact] = []
        catalog = {
            "raw_event_log_jsonl": ("raw", "source_of_truth_extract", "raw_event_log.jsonl", "application/x-ndjson"),
            "trial_summary_csv": ("raw", "source_of_truth_extract", "trial_summary.csv", "text/csv"),
            "block_questionnaire_csv": ("raw", "source_of_truth_extract", "block_questionnaire.csv", "text/csv"),
            "session_summary_csv": ("raw", "source_of_truth_extract", "session_summary.csv", "text/csv"),
            "session_summary_json": ("raw", "source_of_truth_extract", "session_summary.json", "application/json"),
            "trial_level_csv": ("derived", "derived_analysis_artifact", "trial_level.csv", "text/csv"),
            "participant_summary_csv": (
                "derived",
                "derived_analysis_artifact",
                "participant_summary.csv",
                "text/csv",
            ),
            "mixed_effects_ready_csv": (
                "derived",
                "derived_analysis_artifact",
                "mixed_effects_ready.csv",
                "text/csv",
            ),
            "pilot_summary_md": ("report", "derived_analysis_artifact", "pilot_summary.md", "text/markdown"),
        }
        for artifact_type, (category, data_layer, filename, media_type) in catalog.items():
            path = export_dir / filename
            content = payloads.get(artifact_type, "")
            path.write_text(content, encoding="utf-8")
            artifacts.append(
                ExportArtifact(
                    artifact_type=artifact_type,
                    category=category,
                    data_layer=data_layer,
                    filename=filename,
                    media_type=media_type,
                    relative_path=str(path.relative_to(self.export_root)),
                    size_bytes=path.stat().st_size,
                    available=bool(content),
                )
            )

        incomplete_sources = [name for name, count in source_data.items() if count == 0]

        manifest = {
            "manifest_version": self.MANIFEST_VERSION,
            "run_id": run_id,
            "scope": {"scope_level": "run", "run_id": run_id},
            "generated_at": generated_at,
            "export_state": "available" if source_data["session_rows"] > 0 else "empty",
            "artifact_policy": "replace_current",
            "source_of_truth_counts": source_data,
            "provenance": {
                "source_tables": [
                    "participant_sessions",
                    "session_trials",
                    "trial_summary_logs",
                    "trial_event_logs",
                    "block_questionnaires",
                ],
                "derived_from_artifacts": [
                    "trial_summary_csv",
                    "session_summary_csv",
                    "block_questionnaire_csv",
                ],
            },
            "completeness": {
                "incomplete_source_streams": incomplete_sources,
                "warnings_present": bool(warnings),
            },
            "warnings": warnings,
            "artifacts": [asdict(item) for item in artifacts],
        }
        (export_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return [asdict(item) for item in artifacts]


def _to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
