"""Deterministic randomization helpers for pilot sessions."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from packages.shared_types.pilot_types import ExperimentConfig, StimulusItem
from pilot.config_loader import load_latin_square_orders

DEFAULT_LATIN_PATH = "pilot/configs/latin_square_orders.yaml"
MAIN_MODEL_WRONG_TARGET_SHARE = 1 / 3


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

    if not stimuli:
        raise ValueError("cannot build trial plan from an empty stimulus bank")

    practice_trials = _build_practice_trials(experiment.practice_trials, stimuli, rng=rng)
    plan.extend(practice_trials)

    main_trials = _build_main_trials(experiment, assigned_conditions, stimuli, rng=rng)
    plan.extend(main_trials)
    return plan


def _base_features(stimulus: StimulusItem) -> dict[str, Any]:
    return {
        "model_confidence": stimulus.model_confidence,
        "difficulty_prior": stimulus.difficulty_prior,
    }


def _build_practice_trials(practice_trials: int, stimuli: list[StimulusItem], *, rng: random.Random) -> list[dict[str, Any]]:
    if practice_trials <= 0:
        return []

    # Practice is intentionally separate from main allocation and prefers low-risk items.
    ordered = sorted(
        stimuli,
        key=lambda stim: (
            0 if stim.model_correct else 1,
            {"low": 0, "medium": 1, "high": 2}[stim.difficulty_prior],
            _stable_seed("practice", stim.stimulus_id, str(rng.random())),
        ),
    )
    selected = _take_deterministic(ordered, count=practice_trials, allow_reuse=True)
    practice_reused = len({item.stimulus_id for item in selected}) < len(selected)
    out: list[dict[str, Any]] = []
    for trial_index, stim in enumerate(selected):
        out.append(
            {
                "block_id": "practice",
                "block_index": -1,
                "trial_index": trial_index,
                "condition": "static_help",
                "stimulus": stim.to_dict(),
                "pre_render_features": _base_features(stim)
                | {
                    "allocation_phase": "practice",
                    "allocation_reused_stimulus": practice_reused,
                },
            }
        )
    return out


def _build_main_trials(
    experiment: ExperimentConfig,
    assigned_conditions: list[str],
    stimuli: list[StimulusItem],
    *,
    rng: random.Random,
) -> list[dict[str, Any]]:
    total_main_trials = experiment.n_blocks * experiment.trials_per_block
    unique_required = len(stimuli) >= total_main_trials
    pool = sorted(stimuli, key=lambda stim: _stable_seed("main", stim.stimulus_id, str(rng.random())))

    wrong_pool = [stim for stim in pool if not stim.model_correct]
    correct_pool = [stim for stim in pool if stim.model_correct]
    per_block_wrong_targets = _main_wrong_targets(
        total_main_trials=total_main_trials,
        n_blocks=experiment.n_blocks,
        available_wrong=len(wrong_pool),
        available_correct=len(correct_pool),
        require_unique=unique_required,
    )
    main_sequence = _allocate_main_sequence(
        n_blocks=experiment.n_blocks,
        trials_per_block=experiment.trials_per_block,
        wrong_targets=per_block_wrong_targets,
        wrong_pool=wrong_pool,
        correct_pool=correct_pool,
        require_unique=unique_required,
    )
    flat_main_sequence = [stim for block in main_sequence for stim in block]
    reused_in_main = len({stim.stimulus_id for stim in flat_main_sequence}) < len(flat_main_sequence)
    wrong_per_block = [sum(1 for stim in block if not stim.model_correct) for block in main_sequence]
    out: list[dict[str, Any]] = []
    for block_index, block in enumerate(main_sequence):
        block_id = f"block_{block_index + 1}"
        condition = assigned_conditions[block_index]
        for trial_index, stim in enumerate(block):
            out.append(
                {
                    "block_id": block_id,
                    "block_index": block_index,
                    "trial_index": trial_index,
                    "condition": condition,
                    "stimulus": stim.to_dict(),
                    "pre_render_features": _base_features(stim)
                    | {
                        "allocation_phase": "main",
                        "allocation_reused_stimulus": reused_in_main,
                        "allocation_model_wrong_target": per_block_wrong_targets[block_index],
                        "allocation_model_wrong_count": wrong_per_block[block_index],
                    },
                }
            )
    return out


def _allocate_main_sequence(
    *,
    n_blocks: int,
    trials_per_block: int,
    wrong_targets: list[int],
    wrong_pool: list[StimulusItem],
    correct_pool: list[StimulusItem],
    require_unique: bool,
) -> list[list[StimulusItem]]:
    wrong_work = list(wrong_pool)
    correct_work = list(correct_pool)
    base_pool = wrong_pool + correct_pool
    if not base_pool:
        raise ValueError("cannot build trial plan from an empty stimulus bank")

    blocks: list[list[StimulusItem]] = []
    for block_index in range(n_blocks):
        block_target_wrong = min(wrong_targets[block_index], trials_per_block)
        block_target_total = trials_per_block
        block: list[StimulusItem] = []
        block_diff_counts = {"low": 0, "medium": 0, "high": 0}
        diff_targets = _difficulty_targets(trials_per_block)

        for _ in range(block_target_wrong):
            stim = _pop_balanced_candidate(
                wrong_work,
                fallback_pool=base_pool if not require_unique else None,
                block_diff_counts=block_diff_counts,
                diff_targets=diff_targets,
            )
            block.append(stim)
            block_diff_counts[stim.difficulty_prior] += 1

        while len(block) < block_target_total:
            stim = _pop_balanced_candidate(
                correct_work,
                fallback_pool=base_pool if not require_unique else None,
                block_diff_counts=block_diff_counts,
                diff_targets=diff_targets,
            )
            block.append(stim)
            block_diff_counts[stim.difficulty_prior] += 1
        blocks.append(block)
    return blocks


def _main_wrong_targets(
    *,
    total_main_trials: int,
    n_blocks: int,
    available_wrong: int,
    available_correct: int,
    require_unique: bool,
) -> list[int]:
    """Compute explicit bounded model-wrong targets for main trials only.

    Policy:
    - Main trials target an intentional `MAIN_MODEL_WRONG_TARGET_SHARE`.
    - If wrong supply is low, consume what exists and spread evenly across blocks.
    - If wrong supply is abundant, cap exposure at the share target unless the bank
      composition makes that infeasible under unique allocation.
    - Practice trials are excluded from this targeting policy.
    """
    capped_wrong_total = int(total_main_trials * MAIN_MODEL_WRONG_TARGET_SHARE)
    max_bounded_wrong_total = min(capped_wrong_total, available_wrong, total_main_trials)
    if require_unique:
        # Feasibility floor: when unique main trials are required, we may need extra
        # model-wrong stimuli if there are not enough unique model-correct stimuli.
        min_required_wrong_total = max(0, total_main_trials - available_correct)
    else:
        min_required_wrong_total = 0
    target_wrong_total = max(min_required_wrong_total, max_bounded_wrong_total)
    target_wrong_total = min(target_wrong_total, available_wrong, total_main_trials)
    return _distribute_evenly(total=target_wrong_total, n_bins=n_blocks)


def _difficulty_targets(n: int) -> dict[str, int]:
    ordered = ["low", "medium", "high"]
    base = n // len(ordered)
    remainder = n % len(ordered)
    targets = {level: base for level in ordered}
    for idx in range(remainder):
        targets[ordered[idx]] += 1
    return targets


def _pop_balanced_candidate(
    pool: list[StimulusItem],
    *,
    fallback_pool: list[StimulusItem] | None,
    block_diff_counts: dict[str, int],
    diff_targets: dict[str, int],
) -> StimulusItem:
    source = pool if pool else fallback_pool
    if source is None or not source:
        raise ValueError("insufficient stimulus supply for configured main trials")
    best_idx = 0
    best_score = float("-inf")
    for idx, stim in enumerate(source):
        deficit = diff_targets[stim.difficulty_prior] - block_diff_counts[stim.difficulty_prior]
        score = float(deficit)
        if score > best_score:
            best_score = score
            best_idx = idx
    if source is pool:
        return pool.pop(best_idx)
    return source[best_idx]


def _take_deterministic(items: list[StimulusItem], *, count: int, allow_reuse: bool) -> list[StimulusItem]:
    if count <= 0:
        return []
    if not items:
        raise ValueError("cannot allocate from an empty stimulus bank")
    if not allow_reuse and count > len(items):
        raise ValueError("insufficient unique stimuli for requested allocation")
    out: list[StimulusItem] = []
    idx = 0
    while len(out) < count:
        if idx >= len(items):
            if not allow_reuse:
                break
            idx = 0
        out.append(items[idx])
        idx += 1
    return out


def _distribute_evenly(total: int, n_bins: int) -> list[int]:
    if n_bins <= 0:
        raise ValueError("n_bins must be > 0")
    base = total // n_bins
    remainder = total % n_bins
    out = [base] * n_bins
    for idx in range(remainder):
        out[idx] += 1
    return out
