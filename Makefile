.PHONY: setup test validate run-participant-api run-researcher-api run-participant-web run-researcher-web dry-run run-participant-api run-researcher-api pilot-backup pilot-restore pilot-prelaunch-gate pilot-prelaunch-gate-blackbox

PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PY = $(VENV_DIR)/bin/python
VENV_PIP = $(VENV_DIR)/bin/pip
NPM ?= npm

setup:
	$(PYTHON) -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && python -m pip install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install uvicorn
	cd app/participant_web && $(NPM) install
	cd app/researcher_web && $(NPM) install

test:
	$(VENV_PY) -m pytest -q
	cd app/participant_web && $(NPM) run test
	cd app/researcher_web && $(NPM) run test

validate:
	$(VENV_PY) experiments/run_minimal_validation.py

run-participant-api:
	PILOT_DB_PATH=$${PILOT_DB_PATH:-pilot/sessions/pilot_sessions.sqlite3} $(VENV_PY) -m uvicorn app.participant_api.main:app --reload --host 127.0.0.1 --port 8000

run-researcher-api:
	PILOT_DB_PATH=$${PILOT_DB_PATH:-pilot/sessions/pilot_sessions.sqlite3} $(VENV_PY) -m uvicorn app.researcher_api.main:app --reload --host 127.0.0.1 --port 8001

run-participant-web:
	cd app/participant_web && $(NPM) run dev -- --host 127.0.0.1 --port 5173

run-researcher-web:
	cd app/researcher_web && $(NPM) run dev -- --host 127.0.0.1 --port 5174

dry-run:
	$(VENV_PY) experiments/run_toy_pilot_dry_run.py --config pilot/configs/dry_run_experiment.yaml --output-dir artifacts/pilot_dry_run

pilot-backup:
	$(VENV_PY) scripts/pilot_backup.py --output artifacts/pilot_ops/backups/pilot_backup.json

pilot-restore:
	$(VENV_PY) scripts/pilot_restore.py --backup artifacts/pilot_ops/backups/pilot_backup.json --confirm-destructive

pilot-prelaunch-gate:
	@if [ -z "$${PILOT_RESEARCHER_PASSWORD}" ]; then \
		echo "PILOT_RESEARCHER_PASSWORD is required (no default is allowed for prelaunch gate)."; \
		exit 1; \
	fi
	$(VENV_PY) scripts/pilot_prelaunch_gate.py \
		--db-target "$${PILOT_DB_URL:-$${PILOT_DB_PATH:-pilot/sessions/pilot_sessions.sqlite3}}" \
		--run-slug "$${PILOT_RUN_SLUG}" \
		--output-dir "$${PILOT_GATE_OUTPUT_DIR:-artifacts/pilot_ops/prelaunch_gate}" \
		--researcher-username "$${PILOT_RESEARCHER_USERNAME:-admin}" \
		--researcher-password "$${PILOT_RESEARCHER_PASSWORD}"

pilot-prelaunch-gate-blackbox:
	@if [ -z "$${PILOT_RESEARCHER_PASSWORD}" ]; then \
		echo "PILOT_RESEARCHER_PASSWORD is required (no default is allowed for prelaunch gate)."; \
		exit 1; \
	fi
	$(VENV_PY) scripts/pilot_prelaunch_gate.py \
		--db-target "$${PILOT_DB_URL:-$${PILOT_DB_PATH:-pilot/sessions/pilot_sessions.sqlite3}}" \
		--run-slug "$${PILOT_RUN_SLUG}" \
		--participant-base-url "$${PILOT_PARTICIPANT_BASE_URL:-http://127.0.0.1}" \
		--researcher-base-url "$${PILOT_RESEARCHER_BASE_URL:-http://127.0.0.1:8081}" \
		--output-dir "$${PILOT_GATE_OUTPUT_DIR:-artifacts/pilot_ops/prelaunch_gate}" \
		--researcher-username "$${PILOT_RESEARCHER_USERNAME:-admin}" \
		--researcher-password "$${PILOT_RESEARCHER_PASSWORD}"
