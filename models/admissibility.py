"""Admissibility checks for theorem-facing reduced surrogates."""

from __future__ import annotations

from dataclasses import dataclass

from models.diagnostics import envelope_violation_rate, one_step_mae, out_of_support_rate, rollout_mae


@dataclass
class AdmissibilityThresholds:
    max_one_step_mae: float = 0.15
    max_rollout_mae: float = 0.18
    max_local_gain: float = 1.2
    max_envelope_violations: float = 0.02
    max_out_of_support: float = 0.10


def evaluate_admissibility(model, d_train: list[float], d_eval: list[float], a_eval: list[float], e_eval: list[float], thresholds: AdmissibilityThresholds) -> dict[str, float | bool]:
    one_step = one_step_mae(model, d_eval, a_eval, e_eval)
    rollout = rollout_mae(model, d_eval, a_eval, e_eval)
    local_gain = float(model.local_gain_proxy())
    envelope = envelope_violation_rate(model, d_eval, a_eval, e_eval)
    oos = out_of_support_rate(d_train, d_eval)
    admitted = one_step <= thresholds.max_one_step_mae and rollout <= thresholds.max_rollout_mae and local_gain <= thresholds.max_local_gain and envelope <= thresholds.max_envelope_violations and oos <= thresholds.max_out_of_support
    return {
        "one_step_prediction_error": one_step,
        "rollout_error": rollout,
        "local_gain_proxy": local_gain,
        "envelope_violation_rate": envelope,
        "out_of_support_warning_rate": oos,
        "admitted": admitted,
    }
