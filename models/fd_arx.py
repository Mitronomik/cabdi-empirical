"""Linear ARX-style reduced surrogate for F_d."""

from __future__ import annotations

from dataclasses import dataclass


def _solve_4x4(a, b):
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    n = 4
    for i in range(n):
        pivot = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[pivot] = m[pivot], m[i]
        denom = m[i][i] if abs(m[i][i]) > 1e-9 else 1e-9
        for j in range(i, n + 1):
            m[i][j] /= denom
        for r in range(n):
            if r == i:
                continue
            f = m[r][i]
            for j in range(i, n + 1):
                m[r][j] -= f * m[i][j]
    return [m[i][n] for i in range(n)]


def _fit_linear(xs, ys):
    xtx = [[0.0] * 4 for _ in range(4)]
    xty = [0.0] * 4
    for x, y in zip(xs, ys):
        for i in range(4):
            xty[i] += x[i] * y
            for j in range(4):
                xtx[i][j] += x[i] * x[j]
    return _solve_4x4(xtx, xty)


@dataclass
class LinearARXFd:
    coef_: list[float] | None = None

    def fit(self, d: list[float], a: list[float], e: list[float]) -> "LinearARXFd":
        xs = [[1.0, d[t], a[t], e[t]] for t in range(len(d) - 1)]
        ys = [d[t + 1] for t in range(len(d) - 1)]
        self.coef_ = _fit_linear(xs, ys)
        return self

    def predict_one_step(self, d_t: float, a_t: float, e_t: float) -> float:
        c = self.coef_ or [0.0] * 4
        return c[0] + c[1] * d_t + c[2] * a_t + c[3] * e_t

    def rollout(self, d0: float, a: list[float], e: list[float]) -> list[float]:
        out = [0.0 for _ in a]
        out[0] = d0
        for t in range(1, len(a)):
            out[t] = self.predict_one_step(out[t - 1], a[t - 1], e[t - 1])
        return out

    def local_gain_proxy(self) -> float:
        return abs((self.coef_ or [0.0, 0.0])[1])
