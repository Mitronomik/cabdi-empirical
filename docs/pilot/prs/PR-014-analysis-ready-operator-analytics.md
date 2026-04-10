# PR-014: Analysis-ready operator analytics layer

## Scope

This PR upgrades the pilot diagnostics/export interpretation layer for **confirmatory-ready and narrowing-ready behavior-first analysis**, without expanding claim scope beyond the toy pilot evidence boundary.

Touched areas:
- `analysis/pilot/` analysis outputs and summary framing,
- researcher diagnostics/export service semantics,
- researcher diagnostics UI surfacing,
- this PR doc under `docs/pilot/prs/`.

## What changed

1. **Analysis-ready tables include additional confirmatory covariates**
   - `trial_level` derivation now carries `risk_bucket` and `model_confidence`.
   - `mixed_effects_ready` now includes risk bucket, verification and interaction burden indicators, plus condition-level sample context.

2. **Diagnostics now expose run-level and cohort-level analysis flags**
   - Run-level flags call out gaps that block strict confirmatory interpretation (missing summaries/core fields, incomplete matched-budget basis, stale/lifecycle anomalies).
   - Cohort-level flags call out minimum sample/coverage readiness for mixed-effects use.

3. **Exports now publish explicit interpretation semantics**
   - Export responses include a behavior-first interpretation contract describing what outputs can support and what they cannot justify.

4. **Pilot summary markdown now separates claim discipline and readiness flags**
   - Adds explicit “can justify / cannot justify” language.
   - Includes run-level and cohort-level readiness flag sections when diagnostics JSON is provided.

## Claim discipline

These analytics support:
- behavior-first run/cohort evidence statements,
- support/fail-to-support/narrowing interpretations under toy pilot constraints.

These analytics do **not** support:
- psych/cognition inference,
- physiology-grounded interpretation,
- whole-framework real-world validation claims.
