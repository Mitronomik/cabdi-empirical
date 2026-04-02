"""Policy runtime adapter for participant API services."""

from __future__ import annotations

from packages.shared_types.pilot_types import PolicyDecision, TrialContext
from policies.pilot_rules import build_policy_decision, get_or_assign_trial_risk_state


def render_policy_decision(trial_context: TrialContext) -> tuple[str, dict]:
    """Return frozen risk bucket string and serialized policy decision."""
    risk_state = get_or_assign_trial_risk_state(trial_context)
    decision: PolicyDecision = build_policy_decision(trial_context, risk_state)
    return risk_state.risk_bucket.value, decision.to_dict()
