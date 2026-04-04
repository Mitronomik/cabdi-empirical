# Local setup on macOS

This guide documents the current local developer setup for `cabdi-empirical` as of April 2, 2026.

## Scope and scientific guardrail

- The repository is **dual-mode**: synthetic scaffold + human-pilot MVP services.
- Human-pilot mode is currently a toy pilot for adjudicable observable targets.
- Outputs from synthetic and dry-run flows do **not** constitute real-world validation.

## 1) Prerequisites (macOS)

Install these tools first:

- Python **3.11+** (`python3 --version`)
- Node.js **18+** and npm (`node --version`, `npm --version`)
- Git

Optional but recommended:

- `make` (normally present on macOS with Command Line Tools)

## 2) Clone and enter repo

```bash
git clone <your-fork-or-origin-url> cabdi-empirical
cd cabdi-empirical
```

## 3) Python environment setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn
```

Notes:
- `requirements.txt` includes test/API dependencies used by current code.
- `uvicorn` is required to launch FastAPI apps from the command line.

## 4) Frontend dependency setup

Participant web:
```bash
cd app/participant_web
npm install
cd ../..
```

Researcher web:
```bash
cd app/researcher_web
npm install
cd ../..
```

## 5) Environment variables

Current persistence variables:

- `PILOT_DB_URL` (optional): DB URL for both APIs. Supports:
  - Postgres: `postgresql://user:pass@host:5432/dbname`
  - SQLite URL: `sqlite:///pilot/sessions/pilot_sessions.sqlite3`
- `PILOT_DB_PATH` (optional fallback): path to shared SQLite DB used by both APIs.

Example:

```bash
export PILOT_DB_PATH=pilot/sessions/pilot_sessions.sqlite3
# or for Postgres staging parity:
# export PILOT_DB_URL=postgresql://user:pass@localhost:5432/cabdi_pilot
```

Frontend API base variables (optional overrides):

- participant web: `VITE_API_BASE_URL` (default `http://localhost:8000`)
- researcher web: `VITE_RESEARCHER_API_BASE` (default `http://localhost:8001`)

## 6) Local service ports and URLs

Suggested local defaults:

- Participant API: `http://localhost:8000`
- Researcher API: `http://localhost:8001`
- Participant web (Vite): `http://localhost:5173`
- Researcher web (Vite): `http://localhost:5174`

## 7) Launch commands (manual)

In separate terminals (with virtualenv active where needed):

Participant API:
```bash
uvicorn app.participant_api.main:app --reload --host 127.0.0.1 --port 8000
```

Researcher API:
```bash
uvicorn app.researcher_api.main:app --reload --host 127.0.0.1 --port 8001
```

Participant web:
```bash
cd app/participant_web
export VITE_PARTICIPANT_RUN_ID=<run_id_from_researcher_ui_or_api>
npm run dev -- --host 127.0.0.1 --port 5173
```

Researcher web:
```bash
cd app/researcher_web
npm run dev -- --host 127.0.0.1 --port 5174
```

## 8) Quick smoke test checklist

1. Open participant API health endpoint:
   - `GET http://localhost:8000/health` returns `{ "status": "ok" }`.
2. Open participant web at `http://localhost:5173` and proceed through consent/instructions.
3. Open researcher web at `http://localhost:5174`.
4. In researcher web, upload demo stimulus and create a run.
5. Create a participant session bound to that run (via UI or API).
6. Submit several trials and a block questionnaire.
7. Verify exports/diagnostics endpoint responses.

## 9) What works now vs not implemented yet

### Works now

- Synthetic validation scripts (`run_minimal_validation`, `run_non_monotone_region_scan`).
- Human-pilot participant API with session/trial/questionnaire/export endpoints.
- Human-pilot researcher API for stimuli, runs, diagnostics, exports.
- Participant and researcher React UIs.
- Pilot analysis pipeline and dry-run QA harness.

### Not implemented / limited today

- No production auth/authorization model (MVP only).
- No production deployment packaging/orchestration.
- Persistence supports SQLite (local default) and Postgres (staging-parity backend).
- This repo does not provide real-world/clinical validation claims.

## 10) Troubleshooting

- **`ModuleNotFoundError` on API start**: ensure virtualenv is active and `pip install -r requirements.txt` completed.
- **`uvicorn: command not found`**: run `pip install uvicorn` in the active virtualenv.
- **Frontend cannot reach API**: verify API is running on expected port and set `VITE_API_BASE_URL` / `VITE_RESEARCHER_API_BASE`.
- **SQLite file issues**: set `PILOT_DB_PATH` explicitly to a writable path.
- **Port already in use**: use different `--port` flags and mirror them in frontend env variables.
