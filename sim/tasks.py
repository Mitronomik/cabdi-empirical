"""Adjudicable stylized task family for minimal first validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import math
import random

from sim.observation_models import Observation, observe
from sim.operator_dynamics import OperatorState, RoutingAction, step_operator_dynamics


@dataclass
class StepRecord:
    episode: int
    t: int
    policy_name: str
    observation_mode: str
    difficulty: float
    catastrophic_weight: float
    ai_correct: int
    human_correct: int
    final_correct: int
    commission_error: int
    help_level: float
    verification_depth: float
    compute_units: float
    load: float
    oversight: float
    reliance: float
    behavior_load_proxy: float
    behavior_oversight_proxy: float
    task_evidence: float
    physiology_aux: float | None


@dataclass
class TaskFamilyScenario:
    """Synthetic scenario knobs used for compact robustness sweeps."""

    overload_curvature: float = 1.0
    catastrophic_risk_weight_scale: float = 1.0
    verification_saturation: float = 1.0
    observation_noise: float = 1.0


PolicyFn = Callable[[Observation], RoutingAction]


def _sample_difficulty(rng: random.Random) -> float:
    return rng.betavariate(2.1, 2.0)


def _sample_catastrophic_weight(difficulty: float, rng: random.Random, scale: float) -> float:
    base = 5.0 if difficulty > 0.72 else 1.0
    weight = base + (3.0 if rng.random() < 0.08 else 0.0)
    return max(0.1, weight * scale)


def run_task_family(
    *,
    policy_name: str,
    policy_fn: PolicyFn,
    observation_mode: str,
    seed: int,
    episodes: int,
    horizon: int,
    scenario: TaskFamilyScenario | None = None,
) -> list[StepRecord]:
    rng = random.Random(seed)
    records: list[StepRecord] = []
    scenario = scenario or TaskFamilyScenario()

    for ep in range(episodes):
        state = OperatorState(load=0.35, oversight=0.72, reliance=0.38)
        for t in range(horizon):
            difficulty = _sample_difficulty(rng)
            catastrophic_weight = _sample_catastrophic_weight(difficulty, rng, scenario.catastrophic_risk_weight_scale)
            obs = observe(state, difficulty, observation_mode, rng, noise_scale=scenario.observation_noise)
            action = policy_fn(obs)

            overload = max(state.load - 0.70, 0.0)
            overload_penalty = overload ** scenario.overload_curvature
            ai_acc = max(0.05, min(0.95, 0.58 + 0.30 * action.help_level - 0.30 * difficulty - 0.26 * overload_penalty))

            verification_gain = 1.0 - math.exp(-scenario.verification_saturation * action.verification_depth)
            human_acc = max(0.05, min(0.95, 0.67 - 0.25 * state.load + 0.20 * state.oversight - 0.28 * difficulty + 0.12 * verification_gain))
            ai_correct = 1 if rng.random() < ai_acc else 0
            human_correct = 1 if rng.random() < human_acc else 0

            blind_acceptance = state.reliance > 0.58 and action.verification_depth < 0.2
            use_ai = action.help_level > 0.45 and (blind_acceptance or state.oversight < 0.42)
            final_correct = ai_correct if use_ai else human_correct
            commission_error = 1 if use_ai and ai_correct == 0 else 0

            records.append(StepRecord(ep, t, policy_name, observation_mode, difficulty, catastrophic_weight, ai_correct, human_correct, final_correct, commission_error, action.help_level, action.verification_depth, action.compute_units, state.load, state.oversight, state.reliance, obs.behavior_load_proxy, obs.behavior_oversight_proxy, obs.task_evidence, obs.physiology_aux))
            state = step_operator_dynamics(state, action, difficulty, rng)
    return records
