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
- Researcher API docs: disabled in PR-13 (admin surface no longer publicly introspectable)
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

- Both APIs share one DB target. Default remains SQLite (`pilot/sessions/pilot_sessions.sqlite3`) via `PILOT_DB_PATH`.
- For staging-parity runs, set `PILOT_DB_URL` to Postgres (for example: `postgresql://user:pass@localhost:5432/cabdi_pilot`).
- Researcher/admin auth bootstrap defaults (local only): username `admin`, password `admin1234`.
- Override researcher/admin bootstrap credentials with `PILOT_RESEARCHER_USERNAME` and `PILOT_RESEARCHER_PASSWORD`.
- In production-like mode (`PILOT_ENV=production|staging`), set `PILOT_RESEARCHER_PASSWORD` and `PILOT_RESEARCHER_SESSION_SECRET` explicitly.
- Participant session creation is run-bound: `POST /api/v1/sessions` requires `run_slug` (public entry), and only `active` runs accept new participant sessions.
- Participant web entry now uses public slug (via `?run_slug=<public-slug>` or manual input in instructions); optional local default can be set with `VITE_PARTICIPANT_RUN_SLUG`.
- Researcher run creation defaults to `draft`; run must be explicitly activated (`POST /admin/api/v1/runs/{run_id}/activate`) before participant session creation is allowed.

## 9) Current limitations

- MVP local mode only (minimal researcher auth added; no reverse-proxy or hardened deployment controls yet).
- Scientific interpretation remains bounded to synthetic/dry-run claims as documented in repository guidance.
