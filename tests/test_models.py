"""Model tests: the hand-written likelihoods must recover known parameters from simulated data,
and the feature builder must not leak information from after the cutoff."""

import numpy as np
import pandas as pd

from retail.analysis import churn, clv


def simulate_bgnbd(n, r, alpha, a, b, T, seed=0):
    """Generate (x, t_x, T) from the BG/NBD generative story."""
    rng = np.random.default_rng(seed)
    lam = rng.gamma(r, 1 / alpha, n)
    p = rng.beta(a, b, n)
    xs, txs = np.zeros(n), np.zeros(n)
    for i in range(n):
        t, x, alive = 0.0, 0, True
        while alive:
            t += rng.exponential(1 / lam[i])
            if t > T:
                break
            x += 1
            txs[i] = t
            alive = rng.random() > p[i]
        xs[i] = x
    return xs, txs, np.full(n, T)


def test_bgnbd_recovers_parameters():
    true = {"r": 0.7, "alpha": 9.0, "a": 0.3, "b": 2.5}
    x, t_x, T = simulate_bgnbd(4000, T=100, seed=1, **true)
    m = clv.BGNBD().fit(x, t_x, T)
    assert abs(m.r - true["r"]) / true["r"] < 0.15
    assert abs(m.alpha - true["alpha"]) / true["alpha"] < 0.2
    # Population mean dropout probability a/(a+b) is identified more tightly than a and b alone.
    assert abs(m.a / (m.a + m.b) - 0.3 / 2.8) < 0.03


def test_bgnbd_predictions_are_sane():
    m = clv.BGNBD(r=0.7, alpha=9.0, a=0.3, b=2.5)
    x, t_x, T = np.array([0, 5, 5]), np.array([0.0, 50.0, 95.0]), np.array([100.0, 100.0, 100.0])
    p = m.p_alive(x, t_x, T)
    assert p[0] == 1.0  # no repeat purchase -> cannot have dropped out yet under BG/NBD
    assert p[2] > p[1]  # same frequency, more recent purchase -> more likely alive
    e = m.expected_purchases(52, x, t_x, T)
    assert (e >= 0).all() and e[2] > e[1]


def test_gamma_gamma_recovers_population_mean():
    rng = np.random.default_rng(2)
    p, q, v, n = 3.0, 4.0, 300.0, 3000
    nu = rng.gamma(q, 1 / v, n)
    x = rng.integers(1, 15, n)
    m = np.array([rng.gamma(p, 1 / nu_i, k).mean() for nu_i, k in zip(nu, x, strict=True)])
    gg = clv.GammaGamma().fit(x, m)
    true_mean = p * v / (q - 1)
    assert abs(gg.p * gg.v / (gg.q - 1) - true_mean) / true_mean < 0.1


def test_propensity_features_do_not_leak():
    orders = pd.DataFrame({
        "customer_key": [1, 1, 1, 2],
        "invoice_no": ["a", "b", "c", "d"],
        "date_key": pd.to_datetime(["2011-01-01", "2011-02-01", "2011-04-15", "2011-01-10"]),
        "order_value": [100.0, 50.0, 999.0, 20.0],
        "country": ["United Kingdom"] * 4,
    })
    f = churn.features_at(orders, pd.Timestamp("2011-03-01"))
    assert f.loc[1, "revenue"] == 150.0  # the April order is after the cutoff
    assert f.loc[1, "n_orders"] == 2
    assert f.loc[1, "label"] == 1  # ...but it does count as the label
    assert f.loc[2, "label"] == 0
