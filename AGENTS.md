# AGENTS.md

## Project identity

This repository contains the empirical validation scaffold for the CABDI v4.5 preprint.

CABDI here is treated as a theorem-first constrained routing framework with:
- a physiology-free theorem layer,
- optional biobehavioral sensing as an incremental channel,
- strong emphasis on admissibility, falsification, and measurement humility.

Do not try to "prove CABDI".
Your job is to build a reproducible empirical package that can:
1. support,
2. falsify,
3. narrow,
or
4. fail to support
specific CABDI claims.

## Dual-mode repository rule

This repository must remain dual-mode:

1. synthetic scaffold mode,
2. human-pilot mode.

Human-pilot mode must be added without breaking or replacing the synthetic scaffold.

Both modes should reuse the same CABDI policy family logic where practical.
Do not fork policy semantics into unrelated synthetic and UI-specific versions.

## Scientific stance

Treat all simulations as synthetic falsification scaffolds, not real-world validation.

Do not overclaim.

Every report, table, or figure must distinguish between:
- synthetic sanity checks,
- minimal first validation,
- future full validation program.

Behavior-first evidence is the default empirical layer.
Physiology-like channels are optional and may only be used as incremental-value layers over strongest non-physiology baselines.

## Source of truth

Primary conceptual source:
- docs/paper/cabdi_v4.5_submission_ready_preprint_revised_v1.md

Primary bibliography source:
- docs/paper/cabdi_bibliography_v6.bib

Legacy seed artifacts:
- legacy_seed/cabdi_v4_5_synthetic_sanity_check.py
- legacy_seed/cabdi_v4_5_synthetic_sanity_check.csv

If implementation choices conflict with the paper, prefer:
1. explicit falsification logic,
2. reproducibility,
3. conservative interpretation,
4. behavior-first routing claims,
over speculative complexity.

## Main empirical goals

Build a minimal but rigorous empirical scaffold for the following CABDI claims:

1. Practical stability over an admissible bounded-sensitivity operator-response class.
2. Existence of non-monotone assistance advantage under overload and catastrophic-risk structure.
3. Behavior-first routing value.
4. Optional physiology only as an incremental-value layer over strongest non-physiology baselines.
5. Admissibility discipline: no physiology-dependent interpretation should leak into theorem-facing behavior-only claims.

## Required implementation structure

Use or extend these directories:

- sim/
- models/
- policies/
- experiments/
- reports/
- tests/
- artifacts/

Do not place substantial new experimental code in docs/ or legacy_seed/.

## Codex standing instructions for human-pilot mode

For work related to the real-task toy pilot / human-pilot mode, also follow:

- `docs/pilot/codex_master_prompt.md`

That document defines the detailed implementation program for:
- dual-mode architecture,
- preserving the synthetic scaffold,
- one shared policy engine,
- human-pilot mode restricted to adjudicable observable targets,
- implementation order:
  1. schemas
  2. policy runtime
  3. API
  4. participant UI
  5. researcher/admin UI
  6. analysis
  7. dry-run QA

Unless explicitly instructed otherwise:
- do not build a separate standalone repo,
- do not move policy logic into the frontend,
- do not broaden human-pilot mode into physiology validation,
- do not present pilot outputs as whole-framework validation.

## Reduced slow routing model F_d

A central goal of this repository is to operationalize the reduced slow routing model family F_d.

You must implement F_d as an admitted family, not as an unspecified black box.

Required admitted model classes:
1. Linear ARX-style reduced state-space surrogate
2. Piecewise-affine surrogate
3. Constrained nonlinear state-space / NARX-style surrogate

For each admitted F_d class, implement:
- fit()
- predict_one_step()
- rollout()
- local_gain_proxy() or similar bounded-sensitivity diagnostic
- admissibility check

An F_d instance is theorem-facing only if it passes all required admissibility checks.

## Admissibility checks for F_d

Every theorem-facing F_d candidate must report:
- one-step prediction error
- rollout error
- local bounded-gain / Lipschitz proxy
- envelope violation rate
- out-of-support warning if applicable

If a candidate fails admissibility checks, do not use it in theorem-facing experiments.
You may still report it as a failed candidate.

## Baselines

At minimum implement and compare:
- static-help baseline
- monotone-help baseline
- CABDI regime-aware non-monotone routing baseline

Where relevant include:
- behavior-only mode
- behavior + optional physiology-like auxiliary mode

## Minimal first validation

Always prioritize a minimal first validation setup before expanding scope.

Minimal first validation must:
- use one adjudicable task family,
- use matched compute budgets,
- use reproducible seeds,
- include runtime diagnostics,
- report catastrophic-risk proxies,
- report recovery lag,
- report oversight-related error proxies,
- report compute usage.

Do not jump to broad multi-task evaluation until minimal first validation is working.

## Reporting rules

All outputs must be reproducible from code and config.

For every experiment produce:
- config file
- random seed
- CSV or parquet output
- concise markdown summary

Reports must clearly separate:
- supported claims
- unsupported claims
- inconclusive claims

Do not summarize synthetic wins as real validation.

## Code style

Use Python 3.11+.
Prefer small, readable modules over framework-heavy abstractions.
Prefer explicit dataclasses and typed interfaces when practical.
Add docstrings for public classes and functions.
Avoid unnecessary dependencies.

Use deterministic seeds wherever possible.

## Tests

Every change that affects simulator logic, policy behavior, metrics, or F_d fitting must include or update tests.

At minimum run:
- unit tests
- any lightweight validation script needed for the modified code

If a command fails, either fix it or explain clearly in the report why it failed.

## Suggested commands

If the repository includes these files, prefer commands in this order:

1. Install:
   pip install -r requirements.txt

2. Run tests:
   pytest -q

3. Run minimal validation:
   python experiments/run_minimal_validation.py

4. Run full suite:
   python experiments/run_full_suite.py

If these commands are missing, create them.

## Safe scientific behavior

Do not introduce claims that exceed the paper’s admissibility discipline.

Do not write language implying:
- proof of real-world human dynamics,
- proof of cognition,
- proof of physiology-grounded truth,
- proof of general human-AI superiority.

Prefer wording like:
- "supports under this synthetic setup"
- "fails to support"
- "consistent with"
- "narrows the claim"
- "demonstrates only in stylized simulation"

## Pull request expectations

When preparing a PR or summary:
- explain exactly what was implemented,
- explain which CABDI claims were targeted,
- list all experiments run,
- list failed checks,
- separate engineering completion from scientific support.

Do not hide inconclusive or negative results.
