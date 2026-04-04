# Service matrix (current repository state)

| Layer | Component | Entrypoint | Run command | Default port/url | Config/env dependencies | Status |
|---|---|---|---|---|---|---|
| Synthetic scaffold | Minimal first validation | `experiments/run_minimal_validation.py` | `python experiments/run_minimal_validation.py` | n/a | Python deps from `requirements.txt` | Runnable |
| Synthetic scaffold | Full suite wrapper | `experiments/run_full_suite.py` | `python experiments/run_full_suite.py` | n/a | Delegates to minimal validation | Runnable |
| Synthetic scaffold | Non-monotone region scan | `experiments/run_non_monotone_region_scan.py` | `python experiments/run_non_monotone_region_scan.py` | n/a | Python deps from `requirements.txt` | Runnable |
| Human-pilot backend | Participant API | `app/participant_api/main.py` | `uvicorn app.participant_api.main:app --reload --host 127.0.0.1 --port 8000` | `http://localhost:8000` | `PILOT_DB_URL` (Postgres or sqlite URL) or `PILOT_DB_PATH` (SQLite path) | Runnable |
| Human-pilot backend | Researcher/Admin API | `app/researcher_api/main.py` | `uvicorn app.researcher_api.main:app --reload --host 127.0.0.1 --port 8001` | `http://localhost:8001` | `PILOT_DB_URL` (Postgres or sqlite URL) or `PILOT_DB_PATH` (SQLite path); `PILOT_RESEARCHER_SESSION_SECRET` in production-like mode; optional bootstrap `PILOT_RESEARCHER_USERNAME` / `PILOT_RESEARCHER_PASSWORD` | Runnable |
| Human-pilot frontend | Participant web | `app/participant_web/src/main.tsx` | `npm run dev -- --host 127.0.0.1 --port 5173` | `http://localhost:5173` | `VITE_API_BASE_URL` optional | Runnable |
| Human-pilot frontend | Researcher web | `app/researcher_web/src/main.tsx` | `npm run dev -- --host 127.0.0.1 --port 5174` | `http://localhost:5174` | `VITE_RESEARCHER_API_BASE` optional | Runnable |
| Dry-run / QA | Toy pilot dry-run harness | `experiments/run_toy_pilot_dry_run.py` | `python experiments/run_toy_pilot_dry_run.py --config pilot/configs/dry_run_experiment.yaml --output-dir artifacts/pilot_dry_run` | n/a | Uses FastAPI TestClient + SQLite + pilot configs | Runnable |
| Analysis | Pilot analysis pipeline | `experiments/run_pilot_analysis.py` | `python experiments/run_pilot_analysis.py ...` | n/a | Input export files required | Runnable |

## Required config files (actively used)

- `pilot/configs/default_experiment.yaml`
- `pilot/configs/dry_run_experiment.yaml`
- `pilot/configs/policy_conditions.yaml`
- `pilot/configs/latin_square_orders.yaml`
- `pilot/stimuli/scam_not_scam_demo.jsonl`

## Notes on synthetic-only vs pilot services

- The synthetic scaffold remains fully script-driven and is independent of UI services.
- Human-pilot mode exists as local MVP APIs + UIs + analysis/dry-run harness.
- Human-pilot mode is still research MVP and not production-hardened.
