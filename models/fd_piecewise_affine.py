"""Piecewise-affine reduced surrogate for F_d."""

from __future__ import annotations

from dataclasses import dataclass

from models.fd_arx import _fit_linear


@dataclass
class PiecewiseAffineFd:
    threshold_: float | None = None
    low_coef_: list[float] | None = None
    high_coef_: list[float] | None = None

    def fit(self, d: list[float], a: list[float], e: list[float]) -> "PiecewiseAffineFd":
        sorted_d = sorted(d[:-1])
        self.threshold_ = sorted_d[len(sorted_d) // 2]
        low_x = []
        low_y = []
        high_x = []
        high_y = []
        for t in range(len(d) - 1):
            x = [1.0, d[t], a[t], e[t]]
            if d[t] <= self.threshold_:
                low_x.append(x)
                low_y.append(d[t + 1])
            else:
                high_x.append(x)
                high_y.append(d[t + 1])
        self.low_coef_ = _fit_linear(low_x, low_y)
        self.high_coef_ = _fit_linear(high_x, high_y)
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
        out[0] = d0
        for t in range(1, len(a)):
            out[t] = self.predict_one_step(out[t - 1], a[t - 1], e[t - 1])
        return out

    def local_gain_proxy(self) -> float:
        low = abs((self.low_coef_ or [0.0, 0.0])[1])
        high = abs((self.high_coef_ or [0.0, 0.0])[1])
        return max(low, high)
