from policies.static_help import make_static_help_policy
from sim.tasks import run_task_family


def test_simulator_is_deterministic_for_seed():
    p = make_static_help_policy()
    rec1 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=7, episodes=2, horizon=5)
    rec2 = run_task_family(policy_name="static", policy_fn=p, observation_mode="behavior_only", seed=7, episodes=2, horizon=5)
    assert [r.final_correct for r in rec1] == [r.final_correct for r in rec2]
