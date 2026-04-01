"""Static matched-budget help baseline."""

from sim.observation_models import Observation
from sim.operator_dynamics import RoutingAction


def make_static_help_policy(help_level: float = 0.55, verification_depth: float = 0.20):
    def _policy(_obs: Observation) -> RoutingAction:
        return RoutingAction(help_level=help_level, verification_depth=verification_depth, compute_units=1.0)

    return _policy
