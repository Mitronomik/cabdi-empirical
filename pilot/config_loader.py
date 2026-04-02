"""Configuration loading and validation for pilot mode.

Note: PyYAML is intentionally not required in this repository.
The .yaml files in PR-1 are JSON-compatible YAML and are parsed via json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.shared_types.pilot_types import ExperimentConfig


def _load_json_compatible_yaml(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path} is not JSON-compatible YAML. "
            "Install a YAML parser or keep these files in JSON-compatible YAML format."
        ) from exc


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load and validate default experiment config."""
    payload = _load_json_compatible_yaml(Path(path))
    return ExperimentConfig.from_dict(payload)


def load_policy_conditions(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load and validate condition map used by future policy runtime."""
    payload = _load_json_compatible_yaml(Path(path))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("policy_conditions must be a non-empty mapping")
    for condition, spec in payload.items():
        if not isinstance(condition, str) or not condition:
            raise ValueError("condition names must be non-empty strings")
        if not isinstance(spec, dict):
            raise ValueError(f"condition {condition} must map to an object")
        if "ui_help_level" not in spec or "ui_verification_level" not in spec:
            raise ValueError(f"condition {condition} missing required UI keys")
    return payload


def load_latin_square_orders(path: str | Path) -> dict[str, list[str]]:
    """Load and validate Latin-square order assignments."""
    payload = _load_json_compatible_yaml(Path(path))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("latin_square_orders must be a non-empty mapping")
    expected_len: int | None = None
    for order_id, order in payload.items():
        if not isinstance(order_id, str) or not order_id:
            raise ValueError("order ids must be non-empty strings")
        if not isinstance(order, list) or not order:
            raise ValueError(f"order {order_id} must be a non-empty list")
        if len(set(order)) != len(order):
            raise ValueError(f"order {order_id} contains duplicate conditions")
        expected_len = expected_len or len(order)
        if len(order) != expected_len:
            raise ValueError("all latin square rows must have equal length")
    return payload


def load_all_pilot_configs(config_dir: str | Path) -> dict[str, Any]:
    """Load all PR-1 pilot config files and perform cross-file checks."""
    root = Path(config_dir)
    experiment = load_experiment_config(root / "default_experiment.yaml")
    policy_conditions = load_policy_conditions(root / "policy_conditions.yaml")
    latin_square_orders = load_latin_square_orders(root / "latin_square_orders.yaml")

    condition_set = set(experiment.conditions)
    missing_conditions = condition_set - set(policy_conditions.keys())
    if missing_conditions:
        raise ValueError(f"Experiment conditions missing from policy_conditions: {sorted(missing_conditions)}")

    for order_id, order in latin_square_orders.items():
        if set(order) != condition_set:
            raise ValueError(
                f"Latin order {order_id} does not match experiment conditions. "
                f"Expected {sorted(condition_set)}, got {sorted(set(order))}"
            )

    return {
        "experiment": experiment,
        "policy_conditions": policy_conditions,
        "latin_square_orders": latin_square_orders,
    }
