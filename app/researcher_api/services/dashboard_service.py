"""Canonical researcher dashboard read model service."""

from __future__ import annotations

from typing import Any

from app.researcher_api.services.diagnostics_service import DiagnosticsService
from app.researcher_api.services.export_service import AdminExportService
from app.researcher_api.services.run_service import RunService

class DashboardService:
    """Build backend-first dashboard payload with explicit run context."""

    def __init__(
        self,
        *,
        run_service: RunService,
        diagnostics_service: DiagnosticsService,
        export_service: AdminExportService,
    ) -> None:
        self.run_service = run_service
        self.diagnostics_service = diagnostics_service
        self.export_service = export_service

    def get_dashboard_payload(self, *, focus_run_id: str | None = None) -> dict[str, Any]:
        runs = self.run_service.list_runs()
        global_snapshot = self._build_global_snapshot(runs)
        focus_run = self._select_focus_run(runs=runs, focus_run_id=focus_run_id)

        blockers = self._build_blockers(runs)
        warnings: list[str] = []
        next_actions: list[dict[str, Any]] = []
        focus_run_snapshot: dict[str, Any] | None = None
        if focus_run is not None:
            focus_run_snapshot = self._build_focus_run_snapshot(focus_run)
            warnings = list(focus_run_snapshot.get("warnings", []))
            next_actions = list(focus_run_snapshot.get("next_actions", []))

        return {
            "global_snapshot": global_snapshot,
            "focus_run_snapshot": focus_run_snapshot,
            "blockers": blockers,
            "warnings": warnings,
            "next_actions": next_actions,
        }

    def _build_global_snapshot(self, runs: list[dict[str, Any]]) -> dict[str, Any]:
        run_counts = {
            "total": len(runs),
            "draft": 0,
            "active": 0,
            "paused": 0,
            "closed": 0,
            "launchable": 0,
            "not_launchable": 0,
        }
        for run in runs:
            status = str(run.get("status") or "draft")
            if status in run_counts:
                run_counts[status] += 1
            if bool(run.get("launchable")):
                run_counts["launchable"] += 1
            else:
                run_counts["not_launchable"] += 1

        rows = self.run_service.store.fetchall(
            """
            SELECT status, COUNT(*) AS n
            FROM participant_sessions
            GROUP BY status
            """,
            (),
        )
        session_counts = {
            "created": 0,
            "in_progress": 0,
            "paused": 0,
            "awaiting_final_submit": 0,
            "finalized": 0,
            "abandoned": 0,
        }
        for row in rows:
            status = str(row.get("status") or "")
            if status == "completed":
                status = "finalized"
            count = int(row.get("n") or 0)
            if status in session_counts:
                session_counts[status] += count
            else:
                session_counts["abandoned"] += count

        session_counts["total"] = int(sum(session_counts.values()))
        return {
            "run_counts": run_counts,
            "session_counts": session_counts,
        }

    def _select_focus_run(self, *, runs: list[dict[str, Any]], focus_run_id: str | None) -> dict[str, Any] | None:
        if not runs:
            return None
        if focus_run_id:
            requested = next((run for run in runs if run["run_id"] == focus_run_id), None)
            if requested is not None:
                return requested
        active = next((run for run in runs if run.get("status") == "active"), None)
        return active if active is not None else runs[0]

    def _build_focus_run_snapshot(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run["run_id"])
        session_payload = self.run_service.list_run_sessions(run_id)
        diagnostics = self.diagnostics_service.get_run_diagnostics(run_id)
        export_payload = self.export_service.export_run(run_id)

        export_artifacts = export_payload.get("artifacts") if isinstance(export_payload.get("artifacts"), list) else []
        export_available_count = sum(1 for item in export_artifacts if bool(item.get("available")))
        operational_summary = (
            session_payload.get("operational_summary")
            if isinstance(session_payload.get("operational_summary"), dict)
            else {}
        )
        stale_session_count = int(operational_summary.get("stale_session_count") or 0)

        warnings: list[str] = []
        warnings.extend(str(item) for item in diagnostics.get("warnings", []) if str(item).strip())

        focus_snapshot = {
            "run_id": run_id,
            "public_slug": run.get("public_slug"),
            "status": run.get("status"),
            "launchable": bool(run.get("launchable")),
            "launchability_reason": run.get("launchability_reason"),
            "counts": session_payload.get("counts", {}),
            "stale_session_count": stale_session_count,
            "operational_summary": operational_summary,
            "export_availability": {
                "state": export_payload.get("export_state", "unknown"),
                "available_artifact_count": export_available_count,
                "artifact_count": len(export_artifacts),
            },
            "warnings": warnings,
        }
        focus_snapshot["next_actions"] = self._build_next_actions(focus_snapshot)
        return focus_snapshot

    def _build_blockers(self, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blockers: list[dict[str, Any]] = []
        for run in runs:
            launchable = bool(run.get("launchable"))
            status = str(run.get("status") or "draft")
            if launchable and status != "draft":
                continue
            blockers.append(
                {
                    "kind": "launchability",
                    "severity": "error" if status == "draft" else "warning",
                    "run_id": run["run_id"],
                    "public_slug": run.get("public_slug"),
                    "run_status": status,
                    "launchable": launchable,
                    "reason": run.get("launchability_reason") or "Run is not launchable.",
                }
            )
        return blockers

    def _build_next_actions(self, focus_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        run_id = str(focus_snapshot["run_id"])
        status = str(focus_snapshot.get("status") or "")
        launchable = bool(focus_snapshot.get("launchable"))
        actions: list[dict[str, Any]] = [
            {"action": "inspect_run", "label": "Inspect run", "page": "run", "target_run_id": run_id},
            {"action": "monitor_sessions", "label": "Monitor sessions", "page": "sessions", "target_run_id": run_id},
            {"action": "open_diagnostics", "label": "Open diagnostics", "page": "diagnostics", "target_run_id": run_id},
            {"action": "download_exports", "label": "Download exports", "page": "exports", "target_run_id": run_id},
        ]
        if status in {"draft", "paused"} and launchable:
            actions.insert(0, {"action": "activate_run", "label": "Activate run", "page": "run", "target_run_id": run_id})
        return actions
