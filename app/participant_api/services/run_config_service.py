"""Run-config normalization and strict execution resolution helpers."""

from __future__ import annotations

from typing import Any

from packages.shared_types.pilot_types import ExperimentConfig


_EXECUTION_FIELDS = {
    "experiment_id",
    "task_family",
    "n_blocks",
    "trials_per_block",
    "practice_trials",
    "conditions",
    "block_order_strategy",
    "budget_matching_mode",
    "risk_proxy_mode",
    "self_confidence_scale",
    "block_questionnaires",
}


def materialize_run_config_for_storage(
    *,
    run_config: dict[str, Any],
    default_experiment: ExperimentConfig,
    experiment_id: str,
    task_family: str,
) -> dict[str, Any]:
    """Persist a run config with an explicit executable `execution` section.

    This is researcher-side normalization only; participant live execution reads
    persisted run config directly and does not touch default experiment files.
    """

    normalized = dict(run_config)
    raw_execution = normalized.get("execution") if isinstance(normalized.get("execution"), dict) else {}
    execution = {**default_experiment.to_dict(), **raw_execution}

    for field in _EXECUTION_FIELDS:
        if field in normalized and field != "experiment_id" and field != "task_family":
            execution[field] = normalized[field]

    execution["experiment_id"] = experiment_id
    execution["task_family"] = task_family
    normalized["execution"] = execution
    return normalized


def resolve_execution_config_from_run(
    *, run_config: dict[str, Any], run_experiment_id: str, run_task_family: str
) -> ExperimentConfig:
    """Resolve strict executable config from persisted run config for live flow."""

    if not isinstance(run_config, dict):
        raise ValueError("run config must be an object")

    execution_payload: dict[str, Any]
    if isinstance(run_config.get("execution"), dict):
        execution_payload = dict(run_config["execution"])
    else:
        execution_payload = dict(run_config)

    missing = sorted(field for field in _EXECUTION_FIELDS if field not in execution_payload)
    if missing:
        raise ValueError(
            "run config is missing executable fields: " + ", ".join(missing)
        )

    execution_payload["experiment_id"] = run_experiment_id
    execution_payload["task_family"] = run_task_family
    return ExperimentConfig.from_dict(execution_payload)
