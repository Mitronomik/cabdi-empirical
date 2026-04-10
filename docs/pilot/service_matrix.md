# Service matrix (current repository state)

| Layer | Component | Entrypoint | Run command | Default port/url | Config/env dependencies | Status |
|---|---|---|---|---|---|---|
| Synthetic scaffold | Minimal first validation | `experiments/run_minimal_validation.py` | `python experiments/run_minimal_validation.py` | n/a | Python deps from `requirements.txt` | Runnable |
| Synthetic scaffold | Full suite wrapper | `experiments/run_full_suite.py` | `python experiments/run_full_suite.py` | n/a | Delegates to minimal validation | Runnable |
| Synthetic scaffold | Non-monotone region scan | `experiments/run_non_monotone_region_scan.py` | `python experiments/run_non_monotone_region_scan.py` | n/a | Python deps from `requirements.txt` | Runnable |
| Human-pilot backend | Participant API | `app/participant_api/main.py` | `uvicorn app.participant_api.main:app --host 0.0.0.0 --port 8000 --proxy-headers` | internal `:8000` (packaged), local `http://localhost:8000` | `PILOT_DB_URL` (required in staging/prod, Postgres-only non-local posture), `PILOT_PARTICIPANT_CORS_ORIGINS` (required in staging/prod) | Runnable |
| Human-pilot backend | Researcher/Admin API | `app/researcher_api/main.py` | `uvicorn app.researcher_api.main:app --host 0.0.0.0 --port 8001 --proxy-headers` | internal `:8001` (packaged), local `http://localhost:8001` | `PILOT_DB_URL` (required in staging/prod, Postgres-only non-local posture), `PILOT_RESEARCHER_CORS_ORIGINS`, `PILOT_RESEARCHER_PASSWORD` (required + strong in staging/prod), `PILOT_RESEARCHER_SESSION_SECRET` (32+ chars, non-placeholder), `PILOT_RESEARCHER_COOKIE_SECURE=true` (staging/prod) | Runnable |
| Human-pilot frontend | Participant web | `app/participant_web/src/main.tsx` | packaged via `deploy/docker/Dockerfile.participant_web` | public via proxy `:80` | `VITE_API_BASE_URL` optional (defaults same-origin) | Runnable |
| Human-pilot frontend | Researcher web | `app/researcher_web/src/main.tsx` | packaged via `deploy/docker/Dockerfile.researcher_web` | private via proxy `127.0.0.1:8081` | `VITE_RESEARCHER_API_BASE` optional (defaults same-origin) | Runnable |
| Reverse proxy | Edge proxy (public/private split) | `deploy/nginx/edge.conf` | `docker compose -f deploy/compose.staging.yml up` | public `:80`, private `127.0.0.1:8081` | Nginx config + compose port posture | Runnable |
| Dry-run / QA | Toy pilot dry-run harness | `experiments/run_toy_pilot_dry_run.py` | `python experiments/run_toy_pilot_dry_run.py --config pilot/configs/dry_run_experiment.yaml --output-dir artifacts/pilot_dry_run` | n/a | Uses FastAPI TestClient + SQLite + pilot configs | Runnable |
| Pre-launch gate | Final launch-readiness sign-off gate (staging smoke/load/checklist) | `scripts/pilot_prelaunch_gate.py` | `python scripts/pilot_prelaunch_gate.py --db-target \"$PILOT_DB_URL\" --run-slug <active-run-slug> --participant-base-url \"http://127.0.0.1\" --researcher-base-url \"http://127.0.0.1:8081\" --run-restore-drill` | n/a | Requires active run slug + researcher credentials + staging DB target (Postgres for launch posture) + black-box HTTP boundary for final sign-off | Runnable |
| Analysis | Pilot analysis pipeline | `experiments/run_pilot_analysis.py` | `python experiments/run_pilot_analysis.py ...` | n/a | Input export files required | Runnable |

## Required config files (actively used)

- `pilot/configs/default_experiment.yaml`
- `pilot/configs/dry_run_experiment.yaml`
- `pilot/configs/policy_conditions.yaml`
- `pilot/configs/latin_square_orders.yaml`
- `pilot/stimuli/scam_not_scam_demo.jsonl`
- `deploy/compose.staging.yml`
- `deploy/env/.env.staging.example`

## Notes on synthetic-only vs pilot services

- The synthetic scaffold remains fully script-driven and independent from deployment packaging.
- Human-pilot mode now supports a minimal staging/VPS-like packaged posture with explicit public/private surface separation.
- Human-pilot mode remains an MVP research platform; deployment packaging is operationally coherent but intentionally minimal.
- Health/readiness boundary for both APIs:
  - `/health` = process liveness (fast, shallow probe).
  - `/ready` = launch-readiness (includes DB connectivity and launch-critical runtime prerequisites).
