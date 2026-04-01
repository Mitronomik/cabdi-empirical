import numpy as np
import pandas as pd

SEED = 2
rng = np.random.default_rng(SEED)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def step(d, risk, policy):
    h, v, mode = policy(d, risk)
    overload = h * max(0.0, d - 0.55) * 2.5
    assist_benefit = h * (1.0 - 1.6 * abs(d - 0.45))
    verify_benefit = v * (0.5 + 0.5 * risk)
    logit = -1.9 + 1.3 * d + 1.3 * risk - 1.15 * assist_benefit - 0.85 * verify_benefit + 1.45 * overload
    err = rng.random() < sigmoid(logit)
    cat = err and risk > 0.75 and rng.random() < np.clip(0.72 - 0.45 * v + 0.25 * overload, 0.0, 1.0)
    comm = err and rng.random() < np.clip(0.6 - 0.45 * v + 0.1 * overload, 0.0, 1.0)
    rec_lag = max(0.0, 0.14 + 0.75 * d + 0.95 * overload - 0.65 * v + rng.normal(0.0, 0.07))
    compute = 1.0 + 1.6 * h + 0.9 * v
    support = max(0.0, 0.35 * h * (1.0 - 1.6 * abs(d - 0.45))) + 0.2 * v
    d_next = np.clip(0.70 * d + 0.22 * risk + 0.30 * overload - 0.24 * support + rng.normal(0.0, 0.045), 0.0, 1.0)
    return {
        "err": float(err),
        "cat": float(cat),
        "comm": float(comm),
        "rec_lag": rec_lag,
        "compute": compute,
        "d_next": d_next,
        "safe": float(mode == "E"),
    }


def pol_static(d, r):
    return 0.45, 0.35, "M"


def pol_monotone(d, r):
    h = float(np.clip(0.10 + 1.00 * d, 0.0, 1.0))
    v = float(np.clip(0.20 + 0.35 * d + 0.15 * r, 0.0, 1.0))
    return h, v, "M" if d < 0.85 else "E"


def pol_cabdi(d, r):
    if d < 0.30:
        return 0.18, 0.28 + 0.12 * r, "L"
    if d < 0.68:
        return 0.78, 0.48 + 0.12 * r, "M"
    return 0.22, 0.88 + 0.06 * r, "E"


def run(policy, episodes=8000, horizon=28):
    rows = []
    for _ in range(episodes):
        d = float(np.clip(rng.normal(0.38, 0.11), 0.0, 1.0))
        risk = float(np.clip(rng.beta(2.0, 2.0), 0.0, 1.0))
        acc = {"task_error": 0.0, "cat_err": 0.0, "comm_err": 0.0, "rec_lag": 0.0, "compute": 0.0, "safe_mode": 0.0}
        high_risk_frac = 0.0
        for t in range(horizon):
            risk = float(np.clip(0.60 * risk + 0.40 * np.clip(rng.beta(2.3, 2.0) + 0.05 * (t % 9 == 0), 0.0, 1.0), 0.0, 1.0))
            if risk > 0.75:
                high_risk_frac += 1.0
            s = step(d, risk, policy)
            d = s["d_next"]
            acc["task_error"] += s["err"]
            acc["cat_err"] += s["cat"]
            acc["comm_err"] += s["comm"]
            acc["rec_lag"] += s["rec_lag"]
            acc["compute"] += s["compute"]
            acc["safe_mode"] += s["safe"]
        rows.append({k: v / horizon for k, v in acc.items()} | {"high_risk_frac": high_risk_frac / horizon})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    policies = {
        "static_help": pol_static,
        "monotone_help": pol_monotone,
        "cabdi_regime": pol_cabdi,
    }
    out = []
    for name, pol in policies.items():
        df = run(pol)
        stats = df.mean().to_dict()
        stats["policy"] = name
        out.append(stats)
    result = pd.DataFrame(out)[["policy", "task_error", "cat_err", "comm_err", "rec_lag", "compute", "safe_mode", "high_risk_frac"]]
    result.to_csv("/mnt/data/cabdi_v4_5_synthetic_sanity_check.csv", index=False)
    print(result.round(6).to_string(index=False))
