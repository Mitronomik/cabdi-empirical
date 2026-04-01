# Empirical Appendix Draft (Synthetic, Conservative)

This appendix summarizes synthetic experiment outputs only. It does not establish real-world validation.

## Setup
- Inputs inspected: minimal first validation artifacts, non-monotone region scan artifacts, and current report markdown files.
- Seeded synthetic runs are treated as falsification scaffolds, not field evidence.
- Output standardization target: `reports/figures/` and `reports/tables/`.

## Baselines
- static-help
- monotone-help
- cabdi-regime-aware non-monotone routing
- observation modes: behavior-only and behavior+optional physiology-like auxiliary channel

## F_d model family
- Linear ARX surrogate
- Piecewise-affine surrogate
- Constrained nonlinear NARX surrogate
- Each candidate is assessed using one-step error, rollout error, local gain proxy, envelope violations, and out-of-support warning rate.

## Diagnostics
- Policy-level: accuracy, catastrophic-risk proxy, commission-error proxy, recovery lag, compute usage.
- F_d admissibility diagnostics are summarized in table + figure assets.
- Region scan includes delta catastrophic-risk (monotone - CABDI) and class labels.

## Main findings (strictly synthetic)
- Behavior-only risk-first ranking in current outputs: `monotone-help` is best in this run.
- F_d diagnostics are available for all three required surrogate classes.
- Existing non-monotone region scan currently does not show regions classified as supporting CABDI non-monotone advantage.

## Limits of synthetic evidence
- No claim about real-world cognition, physiology, or universal human-AI superiority is supported here.
- Synthetic improvements are not translated into deployment claims.
- Results should be interpreted as support/falsification/narrowing only within stylized simulation.

## Supported / unsupported / inconclusive claims
| claim | status | evidence | notes |
|---|---|---|---|
| Behavior-first policy comparison is executable and reproducible in this synthetic setup | supported | policy_metrics_summary.csv | All three baselines ran in behavior-only mode; best risk-first ranking was monotone-help. |
| Admitted F_d model family can be operationalized with diagnostics | supported | fd_admissibility_summary.csv | ARX, piecewise-affine, and constrained NARX each produced admissibility diagnostics. |
| CABDI non-monotone policy is globally stronger across scanned synthetic regions | unsupported | catastrophic_risk_region_comparison.svg + catastrophic_risk_region_scan_summary.csv | Current region scan rows are classified as monotone_stronger. |
| Optional physiology-like input provides reliable incremental value over strongest behavior-only baseline | inconclusive | policy_metrics_summary.csv | Incremental effects exist in this run but are narrow and synthetic-only; no theorem-facing physiology claim. |
