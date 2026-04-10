"""Contracts for pilot policy runtime.

These helpers are backend-facing only and keep UI policy-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.shared_types.pilot_types import RiskBucket


_ALLOWED_LATENCY_BUCKETS = {"low", "medium", "high"}


@dataclass(frozen=True)
class PreRenderRiskFeatures:
    """Explicit, inspectable inputs used to assign pre-render risk bucket."""

    model_confidence: str
    difficulty_prior: str
    recent_error_count_last_3: int
    recent_blind_accept_count_last_3: int
    recent_latency_z_bucket: str

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "PreRenderRiskFeatures":
        """Build and validate pre-render risk features from trial context."""
        feature = cls(
            model_confidence=str(payload["model_confidence"]),
            difficulty_prior=str(payload["difficulty_prior"]),
            recent_error_count_last_3=int(payload.get("recent_error_count_last_3", 0)),
            recent_blind_accept_count_last_3=int(payload.get("recent_blind_accept_count_last_3", 0)),
            recent_latency_z_bucket=str(payload.get("recent_latency_z_bucket", "medium")),
        )
        feature.validate()
        return feature

    def validate(self) -> None:
        if self.model_confidence not in {"low", "medium", "high"}:
            raise ValueError("model_confidence must be one of low/medium/high")
        if self.difficulty_prior not in {"low", "medium", "high"}:
            raise ValueError("difficulty_prior must be one of low/medium/high")
        if self.recent_error_count_last_3 < 0:
            raise ValueError("recent_error_count_last_3 must be >= 0")
        if self.recent_blind_accept_count_last_3 < 0:
            raise ValueError("recent_blind_accept_count_last_3 must be >= 0")
        if self.recent_latency_z_bucket not in _ALLOWED_LATENCY_BUCKETS:
            raise ValueError("recent_latency_z_bucket must be one of low/medium/high")


@dataclass(frozen=True)
class TrialRiskState:
    """Frozen per-trial risk assignment to prevent within-trial recomputation."""

    trial_id: str
    risk_bucket: RiskBucket


@dataclass(frozen=True)
class BudgetTrace:
    """Per-trial realized budget footprint for diagnostics."""

    condition: str
    risk_bucket: RiskBucket
    shown_components_count: int
    shown_text_tokens: int
    display_load_units: int
    interaction_load_units: int
    provenance_cue_units: int
    evidence_available: int
    max_extra_steps: int
    realized_extra_steps: int
    verification_actions: int
    block_id: str | None = None
