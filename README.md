# CABDI Empirical (dual-mode research platform)

This repository is a **dual-mode CABDI research platform** for the CABDI v4.5 preprint:

1. **Synthetic validation mode** (scripted empirical scaffold), and
2. **Human-pilot mode** (run-bound participant/researcher runtime for narrow observable pilot claims).

The repository is used to:
- operationalize the reduced slow routing model family `F_d`,
- compare CABDI-style routing against matched-budget baselines,
- support, narrow, falsify, or fail to support selected CABDI claims under bounded setups.

It does **not** claim whole-framework real-world validation, latent-state truth recovery, or physiology-grounded proof.

## Mode boundaries (what each mode is for)

### Synthetic validation mode
- Purpose: reproducible falsification/support checks in stylized simulation.
- Primary entrypoints: `experiments/run_minimal_validation.py`, `experiments/run_non_monotone_region_scan.py`, `experiments/run_full_suite.py`.
- Outputs: reproducible artifacts under `artifacts/` and markdown summaries under `reports/`.

### Human-pilot mode
- Purpose: local/staging pilot runtime for adjudicable observable task claims with explicit run management.
- Surfaces:
  - participant API + participant web,
  - researcher/admin API + researcher web.
- Pilot flow is **run-based**: create/manage run on researcher surface, launch participant flow against active run, then use diagnostics/exports/analysis.
- This remains a bounded research runtime, not a production SaaS platform.

## Quick start

### Synthetic validation quick start

```bash
pip install -r requirements.txt
pytest -q
python experiments/run_minimal_validation.py
```

### Human-pilot local quick start (four-process dev loop)

```bash
make setup
make run-participant-api
make run-researcher-api
make run-participant-web
make run-researcher-web
```

Then use researcher surface to create/activate a run and launch participants against that run. For end-to-end operator workflow, use the runbook linked below.

## Synthetic outputs

Running minimal validation writes:
- `artifacts/minimal_first_validation/policy_metrics.csv`
- `artifacts/minimal_first_validation/fd_admissibility.csv`
- `artifacts/minimal_first_validation/fd_theorem_facing.csv` (admitted F_d only)
- `artifacts/minimal_first_validation/step_logs.csv`
- `artifacts/minimal_first_validation/catastrophic_risk_comparison.svg`
- `reports/minimal_first_validation.md`

## Operator and maintainer docs

For setup, launch posture, service boundaries, and operator procedures:

- `docs/pilot/local_setup_mac.md`
- `docs/pilot/runbook.md`
- `docs/pilot/service_matrix.md`

The root `Makefile` provides aligned shortcuts:

```bash
make setup
make lint
make format-check
make typecheck
make gate-python  # scoped Python release gate (lint/format/type + critical backend tests)
make frontend-typecheck
make frontend-build
make gate         # standard release gate (Python gate + frontend typecheck/build)
make test         # full Python + frontend test suite
make validate
make run-participant-api
make run-researcher-api
make run-participant-web
make run-researcher-web
make dry-run
make pilot-backup
make pilot-restore
make pilot-prelaunch-gate
make pilot-prelaunch-gate-blackbox
```
