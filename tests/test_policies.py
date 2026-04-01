from policies.cabdi_regime_aware import make_cabdi_regime_policy
from policies.monotone_help import make_monotone_help_policy
from sim.observation_models import Observation


def test_monotone_policy_increases_help_with_load():
    pol = make_monotone_help_policy()
    low = pol(Observation(behavior_load_proxy=0.1, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    high = pol(Observation(behavior_load_proxy=0.9, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    assert high.help_level > low.help_level


def test_cabdi_policy_non_monotone_overload_drop():
    pol = make_cabdi_regime_policy()
    mid = pol(Observation(behavior_load_proxy=0.5, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    over = pol(Observation(behavior_load_proxy=0.9, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    assert over.help_level < mid.help_level
    assert over.verification_depth > mid.verification_depth


def test_cabdi_thresholds_are_configurable():
    pol = make_cabdi_regime_policy(thresholds=(0.30, 0.60))
    mid = pol(Observation(behavior_load_proxy=0.55, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    over = pol(Observation(behavior_load_proxy=0.65, behavior_oversight_proxy=0.7, task_evidence=0.6, physiology_aux=None))
    assert mid.help_level > over.help_level
