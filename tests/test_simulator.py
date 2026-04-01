from policies.static_help import make_static_help_policy
from sim.tasks import TaskFamilyScenario, run_task_family


def test_simulator_is_deterministic_for_seed():
    p = make_static_help_policy()
    rec1 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=7, episodes=2, horizon=5)
    rec2 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=7, episodes=2, horizon=5)
    assert [r.final_correct for r in rec1] == [r.final_correct for r in rec2]


def test_simulator_respects_scenario_knobs_deterministically():
    p = make_static_help_policy()
    scenario = TaskFamilyScenario(observation_noise=1.2, overload_curvature=1.3, catastrophic_risk_weight_scale=0.8, verification_saturation=1.1)
    rec1 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=9, episodes=2, horizon=5, scenario=scenario)
    rec2 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=9, episodes=2, horizon=5, scenario=scenario)
    assert [r.catastrophic_weight for r in rec1] == [r.catastrophic_weight for r in rec2]
    assert [r.behavior_load_proxy for r in rec1] == [r.behavior_load_proxy for r in rec2]
