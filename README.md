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
