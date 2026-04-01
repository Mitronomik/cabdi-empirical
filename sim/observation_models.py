"""Observation channels for behavior-first and optional physiology-like modes."""

from __future__ import annotations

from dataclasses import dataclass
import random

from sim.operator_dynamics import OperatorState


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class Observation:
    behavior_load_proxy: float
    behavior_oversight_proxy: float
    task_evidence: float
    physiology_aux: float | None


def observe(state: OperatorState, difficulty: float, mode: str, rng: random.Random, noise_scale: float = 1.0) -> Observation:
    """Generate synthetic observations under a configurable noise level."""
    behavior_load = _clip(state.load + rng.gauss(0.0, 0.05 * noise_scale))
    behavior_oversight = _clip(state.oversight + rng.gauss(0.0, 0.05 * noise_scale))
    evidence = _clip(1.0 - difficulty + rng.gauss(0.0, 0.04 * noise_scale))

    physiology = None
    if mode == "behavior_plus_physio":
        physiology = _clip(0.6 * state.load + 0.4 * (1.0 - state.oversight) + rng.gauss(0.0, 0.08 * noise_scale))

    return Observation(behavior_load_proxy=behavior_load, behavior_oversight_proxy=behavior_oversight, task_evidence=evidence, physiology_aux=physiology)
