# F_d Operationalization (Synthetic-only, theorem-discipline aware)

This note documents the operationalized reduced slow routing model family **F_d** in this repository.

## Implemented admitted model families

1. **Linear ARX-style surrogate** (`LinearARXFd`)
2. **Piecewise-affine surrogate** (`PiecewiseAffineFd`)
3. **Constrained nonlinear NARX-style surrogate** (`ConstrainedNARXFd`)

Each class exposes:
- `fit()`
- `predict_one_step()`
- `rollout()`
- `local_gain_proxy()`
- `admissibility_check()`

## Admissibility diagnostics used

A theorem-facing candidate is evaluated on:
- one-step prediction error,
- rollout error,
- local bounded-gain proxy,
- envelope violation rate,
- out-of-support warning rate.

Candidates failing thresholds are kept as failed synthetic candidates, but excluded from theorem-facing usage.

## Theorem-facing discipline in experiments

`experiments/run_minimal_validation.py` now writes two separate tables:
- `artifacts/minimal_first_validation/fd_admissibility.csv` (all candidates),
- `artifacts/minimal_first_validation/fd_theorem_facing.csv` (admitted-only candidates).

This keeps theorem-facing interpretation restricted to admitted **F_d** instances.

## Scope and interpretation

This is a synthetic scaffold for falsification/support/narrowing only.
No real-world cognition or physiology-grounded claims are established by these results.
