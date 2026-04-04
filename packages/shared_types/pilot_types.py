"""Typed domain models for human-pilot mode.

These models are intentionally lightweight and rely only on the Python standard library.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

ContentType = str
DifficultyPrior = str
ConfidenceLevel = str

_ALLOWED_CONTENT_TYPES = {"text", "image", "vignette"}
_ALLOWED_DIFFICULTY = {"low", "medium", "high"}
_ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_ALLOWED_RATIONALE = {"none", "inline", "on_click"}
_ALLOWED_VERIFICATION = {"none", "soft_prompt", "forced_checkbox", "forced_second_look"}
_ALLOWED_COMPRESSION = {"none", "medium", "high"}

SESSION_STATUS_CREATED = "created"
SESSION_STATUS_IN_PROGRESS = "in_progress"
SESSION_STATUS_PAUSED = "paused"
SESSION_STATUS_AWAITING_FINAL_SUBMIT = "awaiting_final_submit"
SESSION_STATUS_FINALIZED = "finalized"
SESSION_STATUS_ABANDONED = "abandoned"
# Backward-compatibility status still tolerated when reading legacy rows.
SESSION_STATUS_COMPLETED_LEGACY = "completed"

CANONICAL_SESSION_STATUSES = {
    SESSION_STATUS_CREATED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_PAUSED,
    SESSION_STATUS_AWAITING_FINAL_SUBMIT,
    SESSION_STATUS_FINALIZED,
    SESSION_STATUS_ABANDONED,
}
ALLOWED_SESSION_STATUSES = CANONICAL_SESSION_STATUSES | {SESSION_STATUS_COMPLETED_LEGACY}
TERMINAL_SESSION_STATUSES = {
    SESSION_STATUS_FINALIZED,
    SESSION_STATUS_ABANDONED,
    SESSION_STATUS_COMPLETED_LEGACY,
}
RESUMABLE_SESSION_STATUSES = {
    SESSION_STATUS_CREATED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_PAUSED,
    SESSION_STATUS_AWAITING_FINAL_SUBMIT,
}


class RiskBucket(str, Enum):
    """Pre-render risk bucket used by future policy runtime."""

    LOW = "low"
    MODERATE = "moderate"
    EXTREME = "extreme"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass
class StimulusItem:
    """Adjudicable trial stimulus entry."""

    stimulus_id: str
    task_family: str
    content_type: ContentType
    payload: dict[str, Any]
    true_label: str
    difficulty_prior: DifficultyPrior
    model_prediction: str
    model_confidence: ConfidenceLevel
    model_correct: bool
    eligible_sets: list[str]
    notes: str | None = None

    def validate(self) -> None:
        _require(bool(self.stimulus_id), "stimulus_id must be non-empty")
        _require(bool(self.task_family), "task_family must be non-empty")
        _require(self.content_type in _ALLOWED_CONTENT_TYPES, "invalid content_type")
        _require(isinstance(self.payload, dict), "payload must be a dict")
        _require(bool(self.true_label), "true_label must be non-empty")
        _require(self.difficulty_prior in _ALLOWED_DIFFICULTY, "invalid difficulty_prior")
        _require(bool(self.model_prediction), "model_prediction must be non-empty")
        _require(self.model_confidence in _ALLOWED_CONFIDENCE, "invalid model_confidence")
        _require(isinstance(self.model_correct, bool), "model_correct must be bool")
        _require(isinstance(self.eligible_sets, list) and all(self.eligible_sets), "eligible_sets must contain non-empty values")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StimulusItem":
        item = cls(**data)
        item.validate()
        return item


@dataclass
class ExperimentConfig:
    """Experiment-level task and condition config."""

    experiment_id: str
    task_family: str
    n_blocks: int
    trials_per_block: int
    practice_trials: int
    conditions: list[str]
    block_order_strategy: str
    budget_matching_mode: str
    risk_proxy_mode: str
    self_confidence_scale: str
    block_questionnaires: list[str]

    def validate(self) -> None:
        _require(bool(self.experiment_id), "experiment_id must be non-empty")
        _require(bool(self.task_family), "task_family must be non-empty")
        _require(self.n_blocks > 0, "n_blocks must be > 0")
        _require(self.trials_per_block > 0, "trials_per_block must be > 0")
        _require(self.practice_trials >= 0, "practice_trials must be >= 0")
        _require(bool(self.conditions), "conditions must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        cfg = cls(**data)
        cfg.validate()
        return cfg


@dataclass
class ParticipantSession:
    """Session state for participant API runtime.

    Semantics:
    - ``current_block_index = -1`` means the session has not entered main blocks yet.
      This covers pre-start and practice-only progression.
    - ``current_block_index >= 0`` means the session has progressed into main blocks.
    - ``awaiting_final_submit`` means all required trial/questionnaire work is done but
      the explicit final-submit action has not been completed.
    """

    session_id: str
    participant_id: str
    experiment_id: str
    run_id: str
    assigned_order: str
    stimulus_set_map: dict[str, str]
    current_block_index: int
    current_trial_index: int
    status: str
    started_at: str
    completed_at: str | None
    device_info: dict[str, Any]
    language: str = "en"

    def validate(self) -> None:
        _require(bool(self.session_id), "session_id must be non-empty")
        _require(bool(self.participant_id), "participant_id must be non-empty")
        _require(bool(self.experiment_id), "experiment_id must be non-empty")
        _require(bool(self.run_id), "run_id must be non-empty")
        _require(self.status in ALLOWED_SESSION_STATUSES, "invalid session status")
        _require(self.current_block_index >= -1, "current_block_index must be >= -1")
        _require(self.current_trial_index >= 0, "current_trial_index must be >= 0")
        datetime.fromisoformat(self.started_at)
        _require(self.language in {"en", "ru"}, "language must be en or ru")
        if self.status in {SESSION_STATUS_AWAITING_FINAL_SUBMIT, SESSION_STATUS_FINALIZED, SESSION_STATUS_COMPLETED_LEGACY}:
            _require(self.current_block_index >= 0, "post-trial session state requires current_block_index >= 0")
        if self.completed_at:
            datetime.fromisoformat(self.completed_at)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParticipantSession":
        session = cls(**data)
        session.validate()
        return session


@dataclass
class TrialContext:
    """Pre-render trial context passed to future policy runtime."""

    session_id: str
    participant_id: str
    condition: str
    block_id: str
    trial_id: str
    stimulus: StimulusItem
    recent_history: dict[str, Any]
    pre_render_features: dict[str, Any]

    def validate(self) -> None:
        _require(bool(self.session_id), "session_id must be non-empty")
        _require(bool(self.participant_id), "participant_id must be non-empty")
        _require(bool(self.condition), "condition must be non-empty")
        self.stimulus.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        out = asdict(self)
        out["stimulus"] = self.stimulus.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrialContext":
        raw = dict(data)
        raw["stimulus"] = StimulusItem.from_dict(raw["stimulus"])
        ctx = cls(**raw)
        ctx.validate()
        return ctx


@dataclass
class PolicyDecision:
    """Frontend-facing structured decision contract from future policy runtime."""

    condition: str
    risk_bucket: RiskBucket
    show_prediction: bool
    show_confidence: bool
    show_rationale: str
    show_evidence: bool
    verification_mode: str
    compression_mode: str
    max_extra_steps: int
    ui_help_level: str
    ui_verification_level: str
    budget_signature: dict[str, Any]

    def validate(self) -> None:
        _require(bool(self.condition), "condition must be non-empty")
        _require(self.show_rationale in _ALLOWED_RATIONALE, "invalid show_rationale")
        _require(self.verification_mode in _ALLOWED_VERIFICATION, "invalid verification_mode")
        _require(self.compression_mode in _ALLOWED_COMPRESSION, "invalid compression_mode")
        _require(self.max_extra_steps >= 0, "max_extra_steps must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        out = asdict(self)
        out["risk_bucket"] = self.risk_bucket.value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolicyDecision":
        raw = dict(data)
        raw["risk_bucket"] = RiskBucket(raw["risk_bucket"])
        decision = cls(**raw)
        decision.validate()
        return decision
