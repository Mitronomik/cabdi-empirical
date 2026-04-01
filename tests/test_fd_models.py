import random

from models.fd_arx import LinearARXFd
from models.fd_narx import ConstrainedNARXFd
from models.fd_piecewise_affine import PiecewiseAffineFd


def _data(n=80):
    rng = random.Random(1)
    d = [0.0 for _ in range(n)]
    a = [rng.uniform(0.2, 0.9) for _ in range(n)]
    e = [rng.uniform(0.1, 0.8) for _ in range(n)]
    d[0] = 0.4
    for t in range(1, n):
        d[t] = max(0, min(1, 0.7 * d[t - 1] + 0.2 * a[t - 1] + 0.1 * e[t - 1]))
    return d, a, e


def test_fd_models_fit_predict_rollout():
    d, a, e = _data()
    for model in [LinearARXFd(), PiecewiseAffineFd(), ConstrainedNARXFd()]:
        model.fit(d, a, e)
        p = model.predict_one_step(d[10], a[10], e[10])
        r = model.rollout(d[0], a, e)
        g = model.local_gain_proxy()
        assert 0.0 <= p <= 1.2
        assert len(r) == len(d)
        assert g >= 0.0
