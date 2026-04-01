# Minimal First Validation (Synthetic, Falsification-Oriented)

This report summarizes a stylized simulation only. It does not establish real-world validity.

## Supported claims
- In this stylized setup, `monotone-help` was strongest in behavior-only mode by risk-first ranking.
- Non-monotone routing can be evaluated directly under overload and catastrophic-weighted errors.

## Unsupported claims
- No real-world cognitive, physiological, or universal human-AI performance claim is supported.

## Inconclusive / narrowed claims
- Physiology-like auxiliary channel is only incremental and synthetic in this scaffold.
- Any non-admitted F_d model is excluded from theorem-facing interpretation.

## Policy metrics
| policy | observation_mode | accuracy | catastrophic_risk_proxy | commission_error_proxy | recovery_lag | compute_usage |
|---|---|---|---|---|---|---|
| static-help | behavior_only | 0.5355555555555556 | 1.03 | 0.42055555555555557 | 1.8253275109170306 | 1800.0 |
| monotone-help | behavior_only | 0.5994444444444444 | 0.9011111111111111 | 0.3511111111111111 | 1.7373493975903616 | 1800.0 |
| cabdi-regime-aware | behavior_only | 0.47555555555555556 | 1.14 | 0 | 2.056644880174292 | 1800.0 |
| static-help | behavior_plus_physio | 0.5277777777777778 | 1.03 | 0.43333333333333335 | 1.8240343347639485 | 1800.0 |
| monotone-help | behavior_plus_physio | 0.6422222222222222 | 0.8233333333333334 | 0.32 | 1.6262626262626263 | 1800.0 |
| cabdi-regime-aware | behavior_plus_physio | 0.4588888888888889 | 1.2327777777777778 | 0 | 2.178970917225951 | 1800.0 |

## F_d admissibility diagnostics
| fd_model | one_step_prediction_error | rollout_error | local_gain_proxy | envelope_violation_rate | out_of_support_warning_rate | admitted |
|---|---|---|---|---|---|---|
| linear_arx | 0.03612749737217484 | 0.05511925338885432 | 0.6127735978036858 | 0.0 | 0.0 | True |
| piecewise_affine | 0.03500610296141225 | 0.042036807083977515 | 0.705423936472952 | 0.0 | 0.0 | True |
| constrained_narx | 0.037856362187132744 | 0.045746862641398676 | 0.5993105614503704 | 0.0 | 0.0 | True |