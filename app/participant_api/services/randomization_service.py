"""Deterministic randomization helpers for pilot sessions."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from packages.shared_types.pilot_types import ExperimentConfig, StimulusItem
from pilot.config_loader import load_latin_square_orders

DEFAULT_LATIN_PATH = "pilot/configs/latin_square_orders.yaml"


def _stable_seed(*parts: str) -> int:
    key = "::".join(parts)
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def assign_order_id(participant_id: str, experiment_id: str, latin_square_path: str = DEFAULT_LATIN_PATH) -> tuple[str, list[str]]:
    orders = load_latin_square_orders(latin_square_path)
    order_ids = sorted(orders.keys())
    idx = _stable_seed(participant_id, experiment_id) % len(order_ids)
    order_id = order_ids[idx]
    return order_id, orders[order_id]


def build_trial_plan(
    participant_id: str,
    experiment: ExperimentConfig,
    assigned_conditions: list[str],
    stimuli: list[StimulusItem],
) -> list[dict[str, Any]]:
    rng = random.Random(_stable_seed(participant_id, experiment.experiment_id, "trial_plan"))
    plan: list[dict[str, Any]] = []

    for trial_index in range(experiment.practice_trials):
        stim = rng.choice(stimuli)
        plan.append(
            {
                "block_id": "practice",
                "block_index": -1,
                "trial_index": trial_index,
                "condition": "static_help",
                "stimulus": stim.to_dict(),
                "pre_render_features": _base_features(stim),
            }
        )

    for block_index in range(experiment.n_blocks):
        block_id = f"block_{block_index + 1}"
        condition = assigned_conditions[block_index]
        for trial_index in range(experiment.trials_per_block):
            stim = rng.choice(stimuli)
            plan.append(
                {
                    "block_id": block_id,
                    "block_index": block_index,
                    "trial_index": trial_index,
                    "condition": condition,
                    "stimulus": stim.to_dict(),
                    "pre_render_features": _base_features(stim),
                }
            )
    return plan


def _base_features(stimulus: StimulusItem) -> dict[str, Any]:
    return {
        "model_confidence": stimulus.model_confidence,
        "difficulty_prior": stimulus.difficulty_prior,
    }
