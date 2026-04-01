"""Monotone help policy baseline."""

from sim.observation_models import Observation
from sim.operator_dynamics import RoutingAction


def make_monotone_help_policy():
    def _policy(obs: Observation) -> RoutingAction:
        help_level = min(0.95, max(0.05, 0.20 + 0.75 * obs.behavior_load_proxy))
        verification_depth = 0.12 + 0.25 * obs.behavior_oversight_proxy
        return RoutingAction(help_level=help_level, verification_depth=verification_depth, compute_units=1.0)

    return _policy
