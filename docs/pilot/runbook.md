# CABDI Pilot local runbook

This runbook is an operational sequence for local testing on macOS.

## 1) One-time setup

```bash
make setup
```

If you prefer manual setup, see `docs/pilot/local_setup_mac.md`.

## 2) Validate baseline quality gates

```bash
make test
make validate
```

## 3) Start APIs (separate terminals)

Terminal A:
```bash
make run-participant-api
```

Terminal B:
```bash
make run-researcher-api
```

## 4) Start web clients (separate terminals)

Terminal C:
```bash
make run-participant-web
```

Terminal D:
```bash
make run-researcher-web
```

## 5) Expected local URLs

- Participant API docs: `http://localhost:8000/docs`
- Participant API health: `http://localhost:8000/health`
- Researcher API docs: `http://localhost:8001/docs`
- Participant web: `http://localhost:5173`
- Researcher web: `http://localhost:5174`

## 6) Recommended local dry-run flow

```bash
make dry-run
```

Expected outputs:

- `artifacts/pilot_dry_run/dry_run_summary.json`
- `artifacts/pilot_dry_run/pilot_dry_run.md`
- `artifacts/pilot_dry_run/raw/*`
- `artifacts/pilot_dry_run/analysis/*`

## 7) Analysis/report regeneration (from exported pilot data)

```bash
python experiments/run_pilot_analysis.py \
  --trial-summary-csv <path/to/trial_summary.csv> \
  --event-log-jsonl <path/to/raw_event_log.jsonl> \
  --session-summary-csv <path/to/session_summary.csv> \
  --block-questionnaire-csv <path/to/block_questionnaire.csv> \
  --diagnostics-json <path/to/diagnostics.json> \
  --output-dir artifacts/pilot_analysis_manual
```

## 8) Service behavior notes

- Both APIs share one SQLite DB by default (`pilot/sessions/pilot_sessions.sqlite3`) via `PILOT_DB_PATH`.
- Participant session creation is run-bound: `POST /api/v1/sessions` requires `run_slug` (public entry), and only `active` runs accept new participant sessions.
- Participant web entry now uses public slug (via `?run_slug=<public-slug>` or manual input in instructions); optional local default can be set with `VITE_PARTICIPANT_RUN_SLUG`.
- Researcher run creation defaults to `draft`; run must be explicitly activated (`POST /admin/api/v1/runs/{run_id}/activate`) before participant session creation is allowed.

## 9) Current limitations

- MVP local mode only (no auth, no hardened ops).
- Scientific interpretation remains bounded to synthetic/dry-run claims as documented in repository guidance.
