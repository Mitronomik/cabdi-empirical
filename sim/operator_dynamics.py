"""Synthetic operator-state dynamics for minimal CABDI validation."""

from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass
class OperatorState:
    load: float
    oversight: float
    reliance: float


@dataclass
class RoutingAction:
    help_level: float
    verification_depth: float
    compute_units: float


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def step_operator_dynamics(state: OperatorState, action: RoutingAction, env_difficulty: float, rng: random.Random) -> OperatorState:
    load = 0.78 * state.load + 0.22 * env_difficulty + 0.35 * action.help_level
    load -= 0.18 * action.verification_depth
    load += rng.gauss(0.0, 0.03)

    oversight = 0.82 * state.oversight + 0.24 * action.verification_depth
    oversight -= 0.16 * max(load - 0.72, 0.0)
    oversight += rng.gauss(0.0, 0.02)

    reliance = 0.85 * state.reliance + 0.16 * action.help_level
    reliance -= 0.11 * action.verification_depth
    reliance += rng.gauss(0.0, 0.02)

    return OperatorState(load=_clip(load), oversight=_clip(oversight), reliance=_clip(reliance))
