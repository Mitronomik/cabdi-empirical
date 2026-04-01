# CABDI Empirical Scaffold

This repository contains a synthetic empirical validation scaffold for the CABDI v4.5 preprint.

It is designed to:
- operationalize the reduced slow routing model family F_d,
- compare CABDI-style routing against matched-budget baselines,
- support, narrow, or falsify selected CABDI claims in stylized simulation.

It does NOT establish real-world validation.

## Quick start

```bash
pip install -r requirements.txt
pytest -q
python experiments/run_minimal_validation.py
```

## Outputs

Running minimal validation writes:
- `artifacts/minimal_first_validation/policy_metrics.csv`
- `artifacts/minimal_first_validation/fd_admissibility.csv`
- `artifacts/minimal_first_validation/step_logs.csv`
- `artifacts/minimal_first_validation/catastrophic_risk_comparison.svg`
- `reports/minimal_first_validation.md`
