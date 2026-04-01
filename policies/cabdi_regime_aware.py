"""CABDI-style non-monotone regime-aware routing baseline."""

from sim.observation_models import Observation
from sim.operator_dynamics import RoutingAction


def make_cabdi_regime_policy(use_physiology: bool = False, thresholds: tuple[float, float] = (0.40, 0.72)):
    """Create a non-monotone policy with configurable regime thresholds."""
    low_threshold, overload_threshold = thresholds

    def _policy(obs: Observation) -> RoutingAction:
        overload_idx = obs.behavior_load_proxy
        if use_physiology and obs.physiology_aux is not None:
            overload_idx = 0.6 * overload_idx + 0.4 * obs.physiology_aux

        if overload_idx < low_threshold:
            help_level, verification = 0.45, 0.20
        elif overload_idx < overload_threshold:
            help_level, verification = 0.85, 0.22
        else:
            help_level, verification = 0.35, 0.55

        return RoutingAction(help_level=help_level, verification_depth=verification, compute_units=1.0)

    return _policy
