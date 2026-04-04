# CABDI Pilot runbook

This runbook now includes both local development and staging/VPS-like deployment posture for PR-14.

## 1) One-time local developer setup

```bash
make setup
```

If you prefer manual setup, see `docs/pilot/local_setup_mac.md`.

## 2) Validate baseline quality gates

```bash
make test
make validate
```

## 3) Local development mode (split terminals)

Terminal A:
```bash
make run-participant-api
```

Terminal B:
```bash
make run-researcher-api
```

Terminal C:
```bash
make run-participant-web
```

Terminal D:
```bash
make run-researcher-web
```

## 4) Staging/VPS-like packaged deployment (Docker Compose)

From repository root:

```bash
cp deploy/env/.env.staging.example deploy/.env
# edit deploy/.env with real secrets/origins
docker compose --env-file deploy/.env -f deploy/compose.staging.yml up --build -d
```

### Packaged topology (trust boundary)

- **Public participant surface**: `edge_proxy` listener on `:80`
  - participant web (`/`)
  - participant API (`/api/*`)
  - participant health (`/health`)
- **Private/protected researcher surface**: `edge_proxy` listener on `127.0.0.1:8081`
  - researcher web (`/`)
  - researcher API (`/admin/api/*`)
- **Database**: Postgres internal-only service (`postgres:5432`) used by both APIs.

TLS is expected to terminate at an outer reverse proxy boundary (for example host-level Nginx/Caddy/ALB). The application stack is launched with proxy-header support.

## 5) Deployment configuration requirements

Required in `deploy/.env` (staging/production-like mode):

- `POSTGRES_PASSWORD`
- `PILOT_PARTICIPANT_CORS_ORIGINS`
- `PILOT_RESEARCHER_CORS_ORIGINS`
- `PILOT_RESEARCHER_PASSWORD`
- `PILOT_RESEARCHER_SESSION_SECRET`

Runtime behavior:

- In `PILOT_ENV=staging|production`, APIs fail fast if required deployment configuration is missing.
- In production-like mode, `PILOT_DB_URL` must be Postgres.
- Researcher session cookie defaults to `Secure=true` in production-like mode.

## 6) Bring-up checks (packaged posture)

```bash
curl -fsS http://127.0.0.1/health
curl -I http://127.0.0.1/
curl -I http://127.0.0.1:8081/
```

Expected:

- participant health returns HTTP 200
- participant web returns HTTP 200
- researcher web is reachable only via private bind (`127.0.0.1:8081` by default)

## 7) Recommended local dry-run flow

```bash
make dry-run
```

Expected outputs:

- `artifacts/pilot_dry_run/dry_run_summary.json`
- `artifacts/pilot_dry_run/pilot_dry_run.md`
- `artifacts/pilot_dry_run/raw/*`
- `artifacts/pilot_dry_run/analysis/*`

## 8) Analysis/report regeneration (from exported pilot data)

```bash
python experiments/run_pilot_analysis.py \
  --trial-summary-csv <path/to/trial_summary.csv> \
  --event-log-jsonl <path/to/raw_event_log.jsonl> \
  --session-summary-csv <path/to/session_summary.csv> \
  --block-questionnaire-csv <path/to/block_questionnaire.csv> \
  --diagnostics-json <path/to/diagnostics.json> \
  --output-dir artifacts/pilot_analysis_manual
```

## 9) Current limitations

- Minimal deployment packaging only (Compose + reverse-proxy posture), not full infrastructure-as-code.
- Researcher protection remains minimal auth + private routing posture; enterprise IAM is out of scope.
- Scientific interpretation remains bounded to synthetic/dry-run claims as documented in repository guidance.

## 10) Backup discipline (repository-owned)

Primary source of truth for pilot runtime state is the pilot database (Postgres in staging/VPS-like mode).

Repository-owned backup command:

```bash
python scripts/pilot_backup.py \
  --db-target "postgresql://<user>:<pass>@<host>:5432/<db>" \
  --output artifacts/pilot_ops/backups/pilot_backup_$(date -u +%Y%m%dT%H%M%SZ).json
```

Notes:

- Backup artifact is a JSON snapshot over critical pilot tables (runs, stimulus sets, sessions, trials, events, summaries, questionnaires, researcher auth table, migrations).
- `schema_version` is embedded in the backup and checked on restore.
- Keep backup artifacts outside ephemeral container filesystems.

## 11) Restore discipline (repository-owned, destructive)

Restore command:

```bash
python scripts/pilot_restore.py \
  --db-target "postgresql://<user>:<pass>@<host>:5432/<db>" \
  --backup artifacts/pilot_ops/backups/<backup_file>.json \
  --confirm-destructive
```

Safety behavior:

- Restore is blocked unless `--confirm-destructive` is provided.
- Restore fails clearly if backup format or schema version is incompatible.
- Restore replaces current pilot table contents with backup contents; do not run against an unknown/untrusted backup artifact.

## 12) Destructive researcher operations safety

- Run close is explicit and confirmation-gated (`confirm_run_id` must match target `run_id`).
- Preferred operator posture is close/archive semantics for runs (not hard-delete in-app).
- If an operator closes a run by mistake, recover via DB restore from a known-good backup.

## 13) Export reproducibility and retention posture

- Source of truth: DB tables (sessions/trials/events/summaries/questionnaires/runs/stimulus sets).
- Derived artifacts: run/session exports and analysis outputs generated from source tables.
- If export files are lost, regenerate by calling export endpoints again or re-running analysis pipeline from restored DB truth.
- Do not treat ad-hoc local CSV/JSON export files as the only retained copy of pilot truth.

## 14) Common failure recovery quick procedures

1. **Service restart:** restart containers/services; committed DB rows remain on persistent Postgres volume.
2. **Accidental run close:** recover by restoring pre-close backup if reopening is required operationally.
3. **Export file loss:** regenerate exports from DB-backed endpoints and re-run analysis script.
4. **DB corruption/operator error:** restore latest valid backup with `scripts/pilot_restore.py --confirm-destructive`.
