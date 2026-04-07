"""Rule-based fake participant simulator for toy pilot dry-run QA."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any


@dataclass(frozen=True)
class FakeParticipantProfile:
    """Simple, explicit behavior profile used by dry-run harness."""

    name: str
    base_follow_model_prob: float
    low_conf_override_boost: float
    reason_click_prob: float
    evidence_open_prob: float
    verification_complete_prob: float
    rt_range_ms: tuple[int, int]
    confidence_range: tuple[int, int]
    response_noise_prob: float


PROFILE_LIBRARY: dict[str, FakeParticipantProfile] = {
    "mostly_compliant": FakeParticipantProfile(
        name="mostly_compliant",
        base_follow_model_prob=0.72,
        low_conf_override_boost=0.15,
        reason_click_prob=0.25,
        evidence_open_prob=0.10,
        verification_complete_prob=0.90,
        rt_range_ms=(850, 1900),
        confidence_range=(60, 95),
        response_noise_prob=0.03,
    ),
    "fast_noisy": FakeParticipantProfile(
        name="fast_noisy",
        base_follow_model_prob=0.62,
        low_conf_override_boost=0.20,
        reason_click_prob=0.08,
        evidence_open_prob=0.04,
        verification_complete_prob=0.65,
        rt_range_ms=(350, 1000),
        confidence_range=(35, 85),
        response_noise_prob=0.18,
    ),
    "cautious_verifier": FakeParticipantProfile(
        name="cautious_verifier",
        base_follow_model_prob=0.55,
        low_conf_override_boost=0.30,
        reason_click_prob=0.70,
        evidence_open_prob=0.55,
        verification_complete_prob=0.97,
        rt_range_ms=(1300, 2800),
        confidence_range=(45, 82),
        response_noise_prob=0.04,
    ),
    "advice_follower": FakeParticipantProfile(
        name="advice_follower",
        base_follow_model_prob=0.86,
        low_conf_override_boost=0.08,
        reason_click_prob=0.15,
        evidence_open_prob=0.08,
        verification_complete_prob=0.80,
        rt_range_ms=(700, 1700),
        confidence_range=(55, 92),
        response_noise_prob=0.05,
    ),
    "low_conf_override": FakeParticipantProfile(
        name="low_conf_override",
        base_follow_model_prob=0.58,
        low_conf_override_boost=0.40,
        reason_click_prob=0.35,
        evidence_open_prob=0.22,
        verification_complete_prob=0.88,
        rt_range_ms=(900, 2200),
        confidence_range=(45, 88),
        response_noise_prob=0.06,
    ),
}


def decide_trial_submission(
    *,
    trial_payload: dict[str, Any],
    profile: FakeParticipantProfile,
    rng: Random,
) -> dict[str, Any]:
    """Build trial submission payload from a trial + profile rules."""
    stimulus = trial_payload["stimulus"]
    decision = trial_payload["policy_decision"]

    model_prediction = stimulus["model_prediction"]
    true_label = stimulus["true_label"]
    model_confidence = stimulus["model_confidence"]

    follow_prob = profile.base_follow_model_prob
    if model_confidence == "low":
        follow_prob = max(0.0, follow_prob - profile.low_conf_override_boost)
    elif model_confidence == "high":
        follow_prob = min(1.0, follow_prob + 0.06)

    if decision.get("verification_mode") in {"forced_checkbox", "forced_second_look"}:
        follow_prob = max(0.0, follow_prob - 0.04)

    follows_model = rng.random() < follow_prob
    human_response = model_prediction if follows_model else true_label

    if rng.random() < profile.response_noise_prob:
        human_response = true_label if human_response == model_prediction else model_prediction

    allows_reason = decision.get("show_rationale", "none") != "none"
    allows_evidence = bool(decision.get("show_evidence", False))
    requires_verification = decision.get("verification_mode", "none") != "none"

    reason_clicked = allows_reason and (rng.random() < profile.reason_click_prob)
    evidence_opened = allows_evidence and (rng.random() < profile.evidence_open_prob)
    verification_completed = (not requires_verification) or (rng.random() < profile.verification_complete_prob)

    rt_min, rt_max = profile.rt_range_ms
    conf_min, conf_max = profile.confidence_range

    event_trace = []
    if reason_clicked:
        event_trace.append({"event_type": "reason_clicked", "payload": {"source": "sim_profile"}})
    if evidence_opened:
        event_trace.append({"event_type": "evidence_opened", "payload": {"source": "sim_profile"}})
    if verification_completed and requires_verification:
        event_trace.append({"event_type": "verification_checked", "payload": {"source": "sim_profile"}})

    return {
        "human_response": human_response,
        "reaction_time_ms": rng.randint(rt_min, rt_max),
        "self_confidence": rng.randint(1, 4),
        "reason_clicked": reason_clicked,
        "evidence_opened": evidence_opened,
        "verification_completed": verification_completed,
        "event_trace": event_trace,
    }
