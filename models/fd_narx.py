"""Constrained nonlinear NARX-style surrogate for F_d."""

from __future__ import annotations

from dataclasses import dataclass


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class ConstrainedNARXFd:
    """Quadratic-feature NARX surrogate with L1-constrained dynamics."""

    coef_: list[float] | None = None
    max_l1: float = 2.0

    def _features(self, d: float, a: float, e: float) -> list[float]:
        return [1.0, d, a, e, d * a, d * e, a * e, d * d, a * a, e * e]

    def fit(self, d: list[float], a: list[float], e: list[float]) -> "ConstrainedNARXFd":
        coef = [0.0] * 10
        lr = 0.05
        for _ in range(600):
            grad = [0.0] * 10
            n = len(d) - 1
            for t in range(n):
                x = self._features(d[t], a[t], e[t])
                pred = sum(coef[i] * x[i] for i in range(10))
                err = pred - d[t + 1]
                for i in range(10):
                    grad[i] += 2.0 * err * x[i] / n
            for i in range(10):
                coef[i] -= lr * grad[i]
            l1 = sum(abs(v) for v in coef[1:])
            if l1 > self.max_l1:
                scale = self.max_l1 / l1
                for i in range(1, 10):
                    coef[i] *= scale
        self.coef_ = coef
        return self

    def predict_one_step(self, d_t: float, a_t: float, e_t: float) -> float:
        x = self._features(d_t, a_t, e_t)
        c = self.coef_ or [0.0] * 10
        return _clip(sum(c[i] * x[i] for i in range(10)))

    def rollout(self, d0: float, a: list[float], e: list[float]) -> list[float]:
        out = [0.0 for _ in a]
        if not out:
            return out
        out[0] = d0
        for t in range(1, len(a)):
            out[t] = self.predict_one_step(out[t - 1], a[t - 1], e[t - 1])
        return out

    def local_gain_proxy(self) -> float:
        c = self.coef_ or [0.0] * 10
        return min(sum(abs(v) for v in c[1:4]) + 0.5 * sum(abs(v) for v in c[4:]), self.max_l1)

    def admissibility_check(self, d_train: list[float], d_eval: list[float], a_eval: list[float], e_eval: list[float], thresholds):
        from models.admissibility import evaluate_admissibility

        return evaluate_admissibility(self, d_train, d_eval, a_eval, e_eval, thresholds)
