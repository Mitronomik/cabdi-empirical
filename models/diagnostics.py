"""Diagnostics for reduced-model admission."""

from __future__ import annotations


def one_step_mae(model, d: list[float], a: list[float], e: list[float]) -> float:
    errs = []
    for t in range(len(d) - 1):
        p = model.predict_one_step(d[t], a[t], e[t])
        errs.append(abs(p - d[t + 1]))
    return sum(errs) / len(errs)


def rollout_mae(model, d: list[float], a: list[float], e: list[float]) -> float:
    pred = model.rollout(d[0], a, e)
    return sum(abs(x - y) for x, y in zip(pred, d)) / len(d)


def envelope_violation_rate(model, d: list[float], a: list[float], e: list[float], lo: float = 0.0, hi: float = 1.0) -> float:
    pred = model.rollout(d[0], a, e)
    v = sum(1 for p in pred if p < lo or p > hi)
    return v / len(pred)


def out_of_support_rate(d_train: list[float], d_eval: list[float]) -> float:
    lo, hi = min(d_train), max(d_train)
    oos = sum(1 for x in d_eval if x < lo or x > hi)
    return oos / len(d_eval)
