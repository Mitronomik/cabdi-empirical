"""Repository-owned pre-launch gate for pilot staging readiness (PR-16)."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.participant_api.persistence.backup_restore import backup_database, restore_database
from app.researcher_api.main import create_app as create_researcher_app


@dataclass
class GateCheck:
    check_id: str
    severity: str  # blocker | warning | info
    passed: bool
    detail: str
    metadata: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_postgres_target(db_target: str) -> bool:
    return db_target.startswith(("postgres://", "postgresql://"))


def _record(
    checks: list[GateCheck],
    *,
    check_id: str,
    severity: str,
    passed: bool,
    detail: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    checks.append(
        GateCheck(
            check_id=check_id,
            severity=severity,
            passed=passed,
            detail=detail,
            metadata=metadata or {},
        )
    )


def _login_researcher(researcher_client: TestClient, username: str, password: str) -> tuple[bool, str]:
    res = researcher_client.post("/admin/api/v1/auth/login", json={"username": username, "password": password})
    if res.status_code != 200:
        return False, f"researcher login failed with status={res.status_code}"
    me = researcher_client.get("/admin/api/v1/auth/me")
    if me.status_code != 200:
        return False, f"researcher auth check failed with status={me.status_code}"
    return True, "researcher auth login + protected /me passed"


def _resolve_active_run(researcher_client: TestClient, run_slug: str) -> tuple[bool, str, str | None]:
    runs_res = researcher_client.get("/admin/api/v1/runs")
    if runs_res.status_code != 200:
        return False, f"failed to list runs; status={runs_res.status_code}", None
    for row in runs_res.json():
        if row.get("public_slug") == run_slug:
            if row.get("status") != "active":
                return False, f"run_slug={run_slug} exists but status={row.get('status')}", row.get("run_id")
            return True, f"run_slug={run_slug} resolved to active run", row.get("run_id")
    return False, f"run_slug={run_slug} not found among researcher runs", None


def _submit_trial(participant: TestClient, session_id: str, trial_payload: dict[str, Any]) -> None:
    submit = participant.post(
        f"/api/v1/sessions/{session_id}/trials/{trial_payload['trial_id']}/submit",
        json={
            "human_response": trial_payload["stimulus"]["true_label"],
            "reaction_time_ms": 900,
            "self_confidence": 65,
            "reason_clicked": False,
            "evidence_opened": False,
            "verification_completed": False,
        },
    )
    submit.raise_for_status()


def _exercise_session_integrity(participant: TestClient, run_slug: str) -> dict[str, Any]:
    create = participant.post(
        "/api/v1/sessions",
        json={"run_slug": run_slug, "language": "en"},
    )
    create.raise_for_status()
    session = create.json()
    session_id = session["session_id"]
    resume_token = session["resume_token"]

    participant.post(f"/api/v1/sessions/{session_id}/start").raise_for_status()

    first_trial = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
    first_trial.raise_for_status()
    _submit_trial(participant, session_id, first_trial.json())

    resume_info = participant.post(
        "/api/v1/sessions/resume-info", json={"run_slug": run_slug, "resume_token": resume_token}
    )
    resume_info.raise_for_status()
    resume_payload = resume_info.json()

    while True:
        nxt = participant.get(f"/api/v1/sessions/{session_id}/next-trial")
        if nxt.status_code == 409:
            block_id = nxt.json()["detail"]["block_id"]
            participant.post(
                f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                json={"burden": 30, "trust": 60, "usefulness": 70},
            ).raise_for_status()
            continue
        nxt.raise_for_status()
        payload = nxt.json()
        if payload.get("status") == "awaiting_final_submit":
            break
        _submit_trial(participant, session_id, payload)

    final_submit = participant.post(f"/api/v1/sessions/{session_id}/final-submit")
    final_submit.raise_for_status()

    resume_after = participant.post(
        "/api/v1/sessions/resume-info", json={"run_slug": run_slug, "resume_token": resume_token}
    )
    resume_after.raise_for_status()

    return {
        "session_id": session_id,
        "resume_before_final": resume_payload,
        "resume_after_final": resume_after.json(),
        "final_submit_status": final_submit.json().get("status"),
    }


def _run_concurrent_smoke(
    *, participant_app: Any, run_slug: str, concurrent_sessions: int, trials_per_session: int
) -> dict[str, Any]:
    def worker(i: int) -> dict[str, Any]:
        with TestClient(participant_app) as client:
            create = client.post(
                "/api/v1/sessions",
                json={"run_slug": run_slug, "language": "en"},
            )
            create.raise_for_status()
            payload = create.json()
            session_id = payload["session_id"]
            resume_token = payload["resume_token"]
            client.post(f"/api/v1/sessions/{session_id}/start").raise_for_status()

            completed = 0
            while completed < trials_per_session:
                nxt = client.get(f"/api/v1/sessions/{session_id}/next-trial")
                if nxt.status_code == 409:
                    block_id = nxt.json()["detail"]["block_id"]
                    client.post(
                        f"/api/v1/sessions/{session_id}/blocks/{block_id}/questionnaire",
                        json={"burden": 25, "trust": 50, "usefulness": 65},
                    ).raise_for_status()
                    continue
                nxt.raise_for_status()
                trial_payload = nxt.json()
                if trial_payload.get("status") in {"awaiting_final_submit", "finalized", "completed"}:
                    break
                _submit_trial(client, session_id, trial_payload)
                completed += 1

            resume = client.post(
                "/api/v1/sessions/resume-info", json={"run_slug": run_slug, "resume_token": resume_token}
            )
            resume.raise_for_status()
            return {
                "session_id": session_id,
                "trials_submitted": completed,
                "resume_status": resume.json().get("resume_status"),
            }

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=concurrent_sessions) as pool:
        futures = [pool.submit(worker, i) for i in range(concurrent_sessions)]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - captured as gate failure metadata
                errors.append(str(exc))

    return {
        "requested_sessions": concurrent_sessions,
        "completed_workers": len(results),
        "errors": errors,
        "results": sorted(results, key=lambda row: row["session_id"]),
    }


def _write_report(output_dir: Path, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "prelaunch_gate_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Pilot Pre-Launch Gate Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Launch ready: `{report['launch_ready']}`",
        f"- Blocking failures: `{len(report['blocking_failures'])}`",
        f"- Warning failures: `{len(report['warning_failures'])}`",
        "",
        "## Checklist",
    ]

    for check in report["checks"]:
        marker = "[PASS]" if check["passed"] else ("[BLOCKER]" if check["severity"] == "blocker" else "[WARN]")
        lines.append(f"- {marker} `{check['check_id']}` — {check['detail']}")

    lines.extend(
        [
            "",
            "## Operator notes",
            "- Blocking failures must be remediated before live launch.",
            "- Warning failures require explicit operator acknowledgement and documented rationale.",
            "",
        ]
    )
    (output_dir / "prelaunch_gate_checklist.md").write_text("\n".join(lines), encoding="utf-8")


def run_prelaunch_gate(
    *,
    db_target: str,
    run_slug: str,
    output_dir: str | Path,
    researcher_username: str,
    researcher_password: str,
    require_postgres: bool = True,
    concurrent_sessions: int = 6,
    concurrent_trials_per_session: int = 3,
    run_restore_drill: bool = False,
) -> dict[str, Any]:
    checks: list[GateCheck] = []
    out_dir = Path(output_dir)

    postgres_ok = _is_postgres_target(db_target)
    _record(
        checks,
        check_id="staging_postgres_posture",
        severity="blocker",
        passed=(postgres_ok if require_postgres else True),
        detail=(
            "Postgres staging posture confirmed"
            if postgres_ok
            else "DB target is not Postgres while pre-launch gate requires staging Postgres posture"
        ),
        metadata={"db_target": db_target, "require_postgres": require_postgres},
    )

    participant_app = create_participant_app(db_target)
    researcher_app = create_researcher_app(db_target)

    with TestClient(participant_app) as participant_client, TestClient(researcher_app) as researcher_client:
        health = participant_client.get("/health")
        _record(
            checks,
            check_id="participant_health",
            severity="blocker",
            passed=health.status_code == 200,
            detail=f"participant health status={health.status_code}",
            metadata={"response": health.json() if health.status_code == 200 else {}},
        )

        auth_ok, auth_detail = _login_researcher(researcher_client, researcher_username, researcher_password)
        _record(
            checks,
            check_id="researcher_auth",
            severity="blocker",
            passed=auth_ok,
            detail=auth_detail,
            metadata={},
        )

        run_ok, run_detail, run_id = _resolve_active_run(researcher_client, run_slug)
        _record(
            checks,
            check_id="active_run_present",
            severity="blocker",
            passed=run_ok,
            detail=run_detail,
            metadata={"run_slug": run_slug, "run_id": run_id},
        )

        run_info = participant_client.get(f"/api/v1/public/runs/{run_slug}")
        slug_ok = run_info.status_code == 200 and bool(run_info.json().get("launchable"))
        _record(
            checks,
            check_id="participant_public_slug_entry",
            severity="blocker",
            passed=slug_ok,
            detail=f"public run lookup status={run_info.status_code}",
            metadata={"public_run": run_info.json() if run_info.status_code == 200 else {}},
        )

        if run_ok and slug_ok:
            integrity = _exercise_session_integrity(participant_client, run_slug)
            resumed = integrity["resume_before_final"].get("resume_status") == "resumable"
            finalized = integrity["resume_after_final"].get("resume_status") == "finalized"
            final_submit_ok = integrity.get("final_submit_status") in {"finalized", "completed"}
            _record(
                checks,
                check_id="session_progress_resume_final_submit",
                severity="blocker",
                passed=(resumed and finalized and final_submit_ok),
                detail="session progression + resume + explicit final submit validated",
                metadata=integrity,
            )

            concurrent = _run_concurrent_smoke(
                participant_app=participant_app,
                run_slug=run_slug,
                concurrent_sessions=concurrent_sessions,
                trials_per_session=concurrent_trials_per_session,
            )
            concurrent_ok = (
                concurrent["completed_workers"] == concurrent["requested_sessions"]
                and not concurrent["errors"]
                and all(row["trials_submitted"] >= 1 for row in concurrent["results"])
            )
            _record(
                checks,
                check_id="concurrent_session_smoke",
                severity="blocker",
                passed=concurrent_ok,
                detail=(
                    f"concurrent smoke completed {concurrent['completed_workers']}/{concurrent['requested_sessions']} sessions"
                ),
                metadata=concurrent,
            )

            if run_id:
                diagnostics = researcher_client.get(f"/admin/api/v1/runs/{run_id}/diagnostics")
                _record(
                    checks,
                    check_id="diagnostics_retrieval",
                    severity="blocker",
                    passed=diagnostics.status_code == 200,
                    detail=f"diagnostics status={diagnostics.status_code}",
                    metadata={"diagnostics": diagnostics.json() if diagnostics.status_code == 200 else {}},
                )

                exports = researcher_client.get(f"/admin/api/v1/runs/{run_id}/exports")
                exports_ok = exports.status_code == 200
                _record(
                    checks,
                    check_id="export_retrieval",
                    severity="blocker",
                    passed=exports_ok,
                    detail=f"run export status={exports.status_code}",
                    metadata={},
                )
                if exports_ok:
                    payload = exports.json()
                    outputs = payload.get("available_outputs", {})
                    analysis_ready = bool(outputs.get("trial_level_csv")) and bool(outputs.get("mixed_effects_ready_csv"))
                    _record(
                        checks,
                        check_id="analysis_ready_outputs",
                        severity="blocker",
                        passed=analysis_ready,
                        detail="analysis-ready outputs are available from run export",
                        metadata={"available_outputs": outputs},
                    )

    backup_path = out_dir / "prelaunch_backup_probe.json"
    try:
        backup_result = backup_database(db_target=db_target, output_path=str(backup_path))
        _record(
            checks,
            check_id="backup_configured",
            severity="blocker",
            passed=True,
            detail="backup snapshot command succeeded",
            metadata={"backup_path": str(backup_path), "row_counts": backup_result.get("row_counts", {})},
        )
    except Exception as exc:
        _record(
            checks,
            check_id="backup_configured",
            severity="blocker",
            passed=False,
            detail=f"backup snapshot failed: {exc}",
            metadata={},
        )

    if run_restore_drill:
        try:
            restore_result = restore_database(
                db_target=db_target,
                backup_path=str(backup_path),
                confirm_destructive=True,
            )
            _record(
                checks,
                check_id="backup_restore_drill",
                severity="blocker",
                passed=True,
                detail="destructive backup restore drill succeeded",
                metadata={"restore_counts": restore_result.get("restored_counts", {})},
            )
        except Exception as exc:
            _record(
                checks,
                check_id="backup_restore_drill",
                severity="blocker",
                passed=False,
                detail=f"backup restore drill failed: {exc}",
                metadata={},
            )
    else:
        _record(
            checks,
            check_id="backup_restore_drill",
            severity="warning",
            passed=False,
            detail="restore drill skipped; run with --run-restore-drill on staging clone before launch",
            metadata={},
        )

    serialized_checks = [asdict(check) for check in checks]
    blocking_failures = [c for c in serialized_checks if c["severity"] == "blocker" and not c["passed"]]
    warning_failures = [c for c in serialized_checks if c["severity"] == "warning" and not c["passed"]]

    report = {
        "generated_at": _utc_now(),
        "db_target": db_target,
        "run_slug": run_slug,
        "launch_ready": len(blocking_failures) == 0,
        "checks": serialized_checks,
        "blocking_failures": blocking_failures,
        "warning_failures": warning_failures,
    }
    _write_report(out_dir, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CABDI pilot pre-launch gate checks")
    parser.add_argument("--db-target", required=True)
    parser.add_argument("--run-slug", required=True)
    parser.add_argument("--output-dir", default="artifacts/pilot_ops/prelaunch_gate")
    parser.add_argument("--researcher-username", default="admin")
    parser.add_argument("--researcher-password", default="admin1234")
    parser.add_argument("--allow-sqlite", action="store_true")
    parser.add_argument("--concurrent-sessions", type=int, default=6)
    parser.add_argument("--concurrent-trials-per-session", type=int, default=3)
    parser.add_argument("--run-restore-drill", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    report = run_prelaunch_gate(
        db_target=args.db_target,
        run_slug=args.run_slug,
        output_dir=args.output_dir,
        researcher_username=args.researcher_username,
        researcher_password=args.researcher_password,
        require_postgres=not args.allow_sqlite,
        concurrent_sessions=max(1, int(args.concurrent_sessions)),
        concurrent_trials_per_session=max(1, int(args.concurrent_trials_per_session)),
        run_restore_drill=args.run_restore_drill,
    )

    if report["blocking_failures"]:
        raise SystemExit("Pre-launch gate failed with blocking checks. See prelaunch_gate_report.json")
    if args.fail_on_warning and report["warning_failures"]:
        raise SystemExit("Pre-launch gate has warnings and --fail-on-warning is set.")


if __name__ == "__main__":
    main()
