"""Runtime diagnostics and falsification-oriented metrics."""

from __future__ import annotations

from statistics import mean


def catastrophic_risk_proxy(records) -> float:
    return mean((1 - r.final_correct) * r.catastrophic_weight for r in records)


def commission_error_proxy(records) -> float:
    return mean(r.commission_error for r in records)


def recovery_lag(records) -> float:
    by_ep = {}
    for r in records:
        by_ep.setdefault(r.episode, []).append(r)
    lags = []
    for recs in by_ep.values():
        streak = 0
        for r in recs:
            if r.final_correct == 0:
                streak += 1
            elif streak > 0:
                lags.append(streak)
                streak = 0
        if streak > 0:
            lags.append(streak)
    return mean(lags) if lags else 0.0


def aggregate_policy_metrics(records) -> dict[str, float]:
    return {
        "accuracy": mean(r.final_correct for r in records),
        "catastrophic_risk_proxy": catastrophic_risk_proxy(records),
        "commission_error_proxy": commission_error_proxy(records),
        "recovery_lag": recovery_lag(records),
        "compute_usage": sum(r.compute_units for r in records),
    }
