"""Logging schemas for future participant API integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

_ALLOWED_EVENT_TYPES = {
    "trial_started",
    "assistance_rendered",
    "reason_clicked",
    "evidence_opened",
    "verification_checked",
    "response_selected",
    "confidence_submitted",
    "trial_completed",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


@dataclass
class TrialEventLog:
    """Event-level trial log item."""

    event_id: str
    session_id: str
    block_id: str
    trial_id: str
    timestamp: str
    event_type: str
    payload: dict[str, Any]

    def validate(self) -> None:
        _require(bool(self.event_id), "event_id must be non-empty")
        _require(bool(self.session_id), "session_id must be non-empty")
        _require(bool(self.block_id), "block_id must be non-empty")
        _require(bool(self.trial_id), "trial_id must be non-empty")
        datetime.fromisoformat(self.timestamp)
        _require(self.event_type in _ALLOWED_EVENT_TYPES, "unsupported event_type")
        _require(isinstance(self.payload, dict), "payload must be a dict")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrialEventLog":
        item = cls(**data)
        item.validate()
        return item


@dataclass
class TrialSummaryLog:
    """Per-trial compact summary for downstream analysis."""

    participant_id: str
    session_id: str
    experiment_id: str
    condition: str
    stimulus_id: str
    task_family: str
    true_label: str
    human_response: str
    correct_or_not: bool
    model_prediction: str
    model_confidence: str
    model_correct_or_not: bool
    risk_bucket: str
    shown_help_level: str
    shown_verification_level: str
    shown_components: list[str]
    accepted_model_advice: bool
    overrode_model: bool
    verification_required: bool
    verification_completed: bool
    reason_clicked: bool
    evidence_opened: bool
    reaction_time_ms: int
    self_confidence: int

    def validate(self) -> None:
        required_text = [
            self.participant_id,
            self.session_id,
            self.experiment_id,
            self.condition,
            self.stimulus_id,
            self.task_family,
            self.true_label,
            self.human_response,
            self.model_prediction,
            self.model_confidence,
            self.risk_bucket,
            self.shown_help_level,
            self.shown_verification_level,
        ]
        _require(all(bool(v) for v in required_text), "required text fields must be non-empty")
        _require(isinstance(self.shown_components, list), "shown_components must be list")
        _require(self.reaction_time_ms >= 0, "reaction_time_ms must be >= 0")
        _require(0 <= self.self_confidence <= 100, "self_confidence must be in [0, 100]")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrialSummaryLog":
        item = cls(**data)
        item.validate()
        return item
