from dataclasses import dataclass

from sim.risk_models import aggregate_policy_metrics


@dataclass
class R:
    final_correct: int
    catastrophic_weight: float
    commission_error: int
    compute_units: float
    episode: int


def test_metrics_fields_exist():
    records = [R(1, 1.0, 0, 1.0, 0), R(0, 2.0, 1, 1.0, 0), R(1, 1.0, 0, 1.0, 1), R(0, 5.0, 1, 1.0, 1)]
    m = aggregate_policy_metrics(records)
    assert {"accuracy", "catastrophic_risk_proxy", "commission_error_proxy", "recovery_lag", "compute_usage"}.issubset(m)
