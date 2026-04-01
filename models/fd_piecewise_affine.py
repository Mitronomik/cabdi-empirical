"""Piecewise-affine reduced surrogate for F_d."""

from __future__ import annotations

from dataclasses import dataclass

from models.fd_arx import _fit_linear


@dataclass
class PiecewiseAffineFd:
    """Two-regime piecewise-affine surrogate split by demand median."""

    threshold_: float | None = None
    low_coef_: list[float] | None = None
    high_coef_: list[float] | None = None

    def fit(self, d: list[float], a: list[float], e: list[float]) -> "PiecewiseAffineFd":
        sorted_d = sorted(d[:-1])
        self.threshold_ = sorted_d[len(sorted_d) // 2]
        low_x: list[list[float]] = []
        low_y: list[float] = []
        high_x: list[list[float]] = []
        high_y: list[float] = []
        pooled_x: list[list[float]] = []
        pooled_y: list[float] = []

        for t in range(len(d) - 1):
            x = [1.0, d[t], a[t], e[t]]
            y = d[t + 1]
            pooled_x.append(x)
            pooled_y.append(y)
            if d[t] <= self.threshold_:
                low_x.append(x)
                low_y.append(y)
            else:
                high_x.append(x)
                high_y.append(y)

        pooled_coef = _fit_linear(pooled_x, pooled_y)
        self.low_coef_ = _fit_linear(low_x, low_y) if low_x else pooled_coef
        self.high_coef_ = _fit_linear(high_x, high_y) if high_x else pooled_coef
        return self

    def _coef(self, d_t: float) -> list[float]:
        if d_t <= (self.threshold_ or 0.0):
            return self.low_coef_ or [0.0] * 4
        return self.high_coef_ or [0.0] * 4

    def predict_one_step(self, d_t: float, a_t: float, e_t: float) -> float:
        c = self._coef(d_t)
        return c[0] + c[1] * d_t + c[2] * a_t + c[3] * e_t

    def rollout(self, d0: float, a: list[float], e: list[float]) -> list[float]:
        out = [0.0 for _ in a]
        if not out:
            return out
        out[0] = d0
        for t in range(1, len(a)):
            out[t] = self.predict_one_step(out[t - 1], a[t - 1], e[t - 1])
        return out

    def local_gain_proxy(self) -> float:
        low = abs((self.low_coef_ or [0.0, 0.0])[1])
        high = abs((self.high_coef_ or [0.0, 0.0])[1])
        return max(low, high)

    def admissibility_check(self, d_train: list[float], d_eval: list[float], a_eval: list[float], e_eval: list[float], thresholds):
        from models.admissibility import evaluate_admissibility

        return evaluate_admissibility(self, d_train, d_eval, a_eval, e_eval, thresholds)
