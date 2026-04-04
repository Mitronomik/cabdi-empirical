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
