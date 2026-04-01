# Non-Monotone CABDI Region Scan (Synthetic Only)

This scan is a small synthetic robustness map. It is not real-world validation.

## Setup
- Compared `cabdi-regime-aware` vs `monotone-help` under matched compute budgets (compute_units=1.0 each step).
- Swept overload curvature, catastrophic-risk weight, verification saturation, observation noise, and CABDI regime thresholds.
- Used deterministic seeds per setting and policy.

## Regions supporting CABDI-style non-monotone advantage
- none

## Regions where monotone-help is stronger
- scan_04: delta_risk=-0.1689, thresholds=early_overload, noise=1.2, sat=1.2
- scan_02: delta_risk=-0.1880, thresholds=early_overload, noise=1.2, sat=0.8
- scan_03: delta_risk=-0.2061, thresholds=default, noise=0.8, sat=1.2

## Regions where outcomes match or are inconclusive
- matches_monotone: 0 settings
- inconclusive: 0 settings

## Interpretation discipline
- These findings only narrow/support/falsify the non-monotone routing claim within stylized simulation.
- No real-world human, cognition, or physiology claim is made.