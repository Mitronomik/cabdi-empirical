import random

from models.admissibility import AdmissibilityThresholds
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


def test_fd_models_emit_required_admissibility_diagnostics():
    d, a, e = _data(n=120)
    split = 80
    d_train, a_train, e_train = d[:split], a[:split], e[:split]
    d_eval, a_eval, e_eval = d[split:], a[split:], e[split:]

    thresholds = AdmissibilityThresholds()
    required = {
        "one_step_prediction_error",
        "rollout_error",
        "local_gain_proxy",
        "envelope_violation_rate",
        "out_of_support_warning_rate",
        "admitted",
    }

    for model in [LinearARXFd(), PiecewiseAffineFd(), ConstrainedNARXFd()]:
        model.fit(d_train, a_train, e_train)
        diagnostics = model.admissibility_check(d_train, d_eval, a_eval, e_eval, thresholds)
        assert required.issubset(diagnostics.keys())
        assert isinstance(diagnostics["admitted"], bool)


def test_piecewise_affine_handles_single_regime_safely():
    d = [0.5 for _ in range(20)]
    a = [0.3 for _ in range(20)]
    e = [0.2 for _ in range(20)]

    model = PiecewiseAffineFd().fit(d, a, e)
    pred = model.predict_one_step(0.5, 0.3, 0.2)
    assert pred == pred  # not nan
