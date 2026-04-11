# CABDI pilot VPS deploy playbook (PR-12)

This playbook is the bounded production-operations companion for the human-pilot mode.
It is VPS-oriented (single operator + Docker Compose) and keeps explicit public/private boundaries.

## 1) Deployment boundary model

Supported model in this repository: **external TLS termination (required)**.

- **Compose exposure on VPS host**:
  - participant edge: `127.0.0.1:8080 -> edge_proxy:8080`
  - researcher edge: `127.0.0.1:8081 -> edge_proxy:8081`
- **Public participant surface (user-facing)**: HTTPS on host edge (for example `https://participant.example.org`) forwarded to `http://127.0.0.1:8080` (`/`, `/api/*`, `/health`, `/ready`).
- **Private researcher surface (operator-facing)**: HTTPS on private edge only (for example VPN/private segment `https://researcher.internal.example.org`) forwarded to `http://127.0.0.1:8081` (`/`, `/admin/api/*`, `/health`, `/ready`).
- **Database**: internal Compose network only (`postgres:5432`), never host-published.
- **Not supported by this stack**: in-container TLS cert management/ACME inside `edge_proxy`.

This repository does **not** define cloud-specific infrastructure templates; it defines a VPS-friendly service posture only.

## 2) HTTPS and secret posture

1. Terminate HTTPS at host edge (outside Compose) and forward internally to `127.0.0.1:8080` (participant) and `127.0.0.1:8081` (researcher).
2. Keep researcher endpoint private (VPN/SSH tunnel/private segment); do not publish `8081` to the public internet.
3. Use only strong non-placeholder secrets in `deploy/.env`:
   - `POSTGRES_PASSWORD`
   - `PILOT_RESEARCHER_PASSWORD`
   - `PILOT_RESEARCHER_SESSION_SECRET` (32+ chars)
4. Keep `PILOT_RESEARCHER_COOKIE_SECURE=true`.
5. Do not commit `deploy/.env`.
- Researcher auth CSRF contract in staging/production: state-changing researcher auth requests must carry an `Origin` header that exactly matches `PILOT_RESEARCHER_CORS_ORIGINS`; missing or mismatched origins are blocked.

## 3) Initial deploy

From repo root:

```bash
cp deploy/env/.env.staging.example deploy/.env
# edit deploy/.env with real secrets + real HTTPS origins

docker compose --env-file deploy/.env -f deploy/compose.staging.yml pull

docker compose --env-file deploy/.env -f deploy/compose.staging.yml up --build -d

docker compose --env-file deploy/.env -f deploy/compose.staging.yml ps
```

## 4) Health/readiness checks

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:8081/ready
```

Expected:
- all endpoints return `200` when services are launch-ready;
- researcher probes are reachable only on private bind.

## 5) Restart procedure

```bash
docker compose --env-file deploy/.env -f deploy/compose.staging.yml restart

docker compose --env-file deploy/.env -f deploy/compose.staging.yml ps
```

If only one service needs restart:

```bash
docker compose --env-file deploy/.env -f deploy/compose.staging.yml restart edge_proxy
```

## 6) Rollback procedure (single-operator practical)

1. Keep previous image tags available locally/registry before upgrade.
2. Re-point compose image/build references to known-good revision (typically by `git checkout <known-good-tag-or-commit>`).
3. Recreate services:

```bash
git checkout <known-good-tag-or-commit>
docker compose --env-file deploy/.env -f deploy/compose.staging.yml up --build -d
```

4. Re-run health/readiness checks.
5. If rollback follows data corruption, run restore procedure below.

## 7) Logging posture

- `edge_proxy` emits structured JSON access logs and warning+ error logs.
- Container logs are rotated via docker `json-file` limits (`10m`, 5 files).

Operator commands:

```bash
docker compose --env-file deploy/.env -f deploy/compose.staging.yml logs --tail=200 edge_proxy

docker compose --env-file deploy/.env -f deploy/compose.staging.yml logs --tail=200 participant_api researcher_api
```

## 8) Backup and restore

Backup:

```bash
python scripts/pilot_backup_rotate.py \
  --db-target "$PILOT_DB_URL" \
  --backup-dir /var/backups/cabdi-pilot \
  --timestamp-utc "$(date -u +%Y%m%dT%H%M%SZ)" \
  --retain-count 14
```

Restore (destructive):

```bash
python scripts/pilot_restore.py \
  --db-target "$PILOT_DB_URL" \
  --backup /var/backups/cabdi-pilot/<backup_file>.json \
  --confirm-destructive
```

## 9) Prelaunch gate (required before operator GO)

```bash
python scripts/pilot_prelaunch_gate.py \
  --db-target "$PILOT_DB_URL" \
  --run-slug "<active-run-slug>" \
  --participant-base-url "http://127.0.0.1:8080" \
  --researcher-base-url "http://127.0.0.1:8081" \
  --researcher-username "${PILOT_RESEARCHER_USERNAME:-admin}" \
  --researcher-password "$PILOT_RESEARCHER_PASSWORD" \
  --run-restore-drill \
  --output-dir artifacts/pilot_ops/prelaunch_gate
```

Decision:
- any blocker => NO-GO;
- zero blockers + acknowledged warnings => GO allowed.
