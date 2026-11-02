"""Customer lifetime value with BG/NBD (purchase frequency) and Gamma-Gamma (spend).

Implemented from the original papers with scipy rather than a library, so every term is visible:
  Fader, Hardie & Lee (2005) "Counting your customers the easy way"
  Fader, Hardie & Lee (2005) "RFM and CLV: using iso-value curves"

Time unit is weeks. A "transaction" is a distinct purchase day per customer, as in the papers.
Validated by fitting on a calibration window and predicting a held-out period.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, hyp2f1

from retail.analysis.common import DATA_END


def summary_data(orders: pd.DataFrame, cal_end: pd.Timestamp, obs_end: pd.Timestamp | None = None):
    """Per customer: x (repeat purchases), t_x (week of last purchase), T (age in weeks),
    monetary (mean value of repeat purchase days), and optional holdout purchase count."""
    daily = orders.groupby(["customer_key", "date_key"], as_index=False)["order_value"].sum()
    cal = daily[daily["date_key"] <= cal_end]
    g = cal.groupby("customer_key")
    first, last = g["date_key"].min(), g["date_key"].max()
    df = pd.DataFrame({
        "x": g.size() - 1,
        "t_x": (last - first).dt.days / 7,
        "T": (cal_end - first).dt.days / 7,
    })
    # Gamma-Gamma uses the mean of *repeat* transactions only (first purchase excluded).
    rep = cal.sort_values("date_key").groupby("customer_key").apply(
        lambda d: d["order_value"].iloc[1:].mean() if len(d) > 1 else np.nan, include_groups=False
    )
    df["monetary"] = rep
    if obs_end is not None:
        hold = daily[(daily["date_key"] > cal_end) & (daily["date_key"] <= obs_end)]
        df["x_holdout"] = hold.groupby("customer_key").size().reindex(df.index, fill_value=0)
        df["value_holdout"] = hold.groupby("customer_key")["order_value"].sum().reindex(df.index, fill_value=0)
    return df[df["T"] > 0]


@dataclass
class BGNBD:
    r: float = 1.0
    alpha: float = 1.0
    a: float = 1.0
    b: float = 1.0

    @staticmethod
    def _ll(params, x, t_x, T):
        r, alpha, a, b = np.exp(params)
        a1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
        a2 = gammaln(a + b) + gammaln(b + x) - gammaln(b) - gammaln(a + b + x)
        a3 = -(r + x) * np.log(alpha + T)
        with np.errstate(divide="ignore", invalid="ignore"):
            a4 = np.where(
                x > 0,
                np.log(a) - np.log(np.maximum(b + x - 1, 1e-12)) - (r + x) * np.log(alpha + t_x),
                -np.inf,
            )
        return -(a1 + a2 + np.logaddexp(a3, a4)).sum()

    def fit(self, x, t_x, T):
        res = minimize(self._ll, np.zeros(4), args=(x, t_x, T), method="Nelder-Mead",
                       options={"maxiter": 5000, "xatol": 1e-6, "fatol": 1e-6})
        self.r, self.alpha, self.a, self.b = np.exp(res.x)
        self.loglik = -res.fun
        return self

    def _odds_dead(self, x, t_x, T):
        r, alpha, a, b = self.r, self.alpha, self.a, self.b
        return np.where(x > 0, a / (b + x - 1) * ((alpha + T) / (alpha + t_x)) ** (r + x), 0.0)

    def p_alive(self, x, t_x, T):
        return 1.0 / (1.0 + self._odds_dead(x, t_x, T))

    def expected_purchases(self, t, x, t_x, T):
        """Conditional expected number of purchases in the next t weeks."""
        r, alpha, a, b = self.r, self.alpha, self.a, self.b
        z = t / (alpha + T + t)
        num = (a + b + x - 1) / (a - 1) * (
            1 - ((alpha + T) / (alpha + T + t)) ** (r + x) * hyp2f1(r + x, b + x, a + b + x - 1, z)
        )
        return num / (1.0 + self._odds_dead(x, t_x, T))


@dataclass
class GammaGamma:
    p: float = 1.0
    q: float = 1.0
    v: float = 1.0

    @staticmethod
    def _ll(params, x, m):
        p, q, v = np.exp(params)
        ll = (gammaln(p * x + q) - gammaln(p * x) - gammaln(q) + q * np.log(v)
              + (p * x - 1) * np.log(m) + p * x * np.log(x) - (p * x + q) * np.log(x * m + v))
        return -ll.sum()

    def fit(self, x, m):
        # Starting at p=q=v=1 lets Nelder-Mead drift into a degenerate p -> inf, v -> 0 ridge;
        # a gradient method from a sensible start converges to the same optimum from any seed.
        res = minimize(self._ll, np.log([2.0, 3.0, 100.0]), args=(x, m), method="L-BFGS-B")
        self.p, self.q, self.v = np.exp(res.x)
        return self

    def expected_spend(self, x, m, population_mean):
        """Posterior mean spend; customers with no repeat purchase get the population mean."""
        p, q, v = self.p, self.q, self.v
        with np.errstate(invalid="ignore"):
            cond = (p * (v + x * m)) / (p * x + q - 1)
        return np.where((x > 0) & np.isfinite(cond), cond, population_mean)


def validate(orders: pd.DataFrame, holdout_weeks: int = 26) -> tuple[pd.DataFrame, dict]:
    cal_end = DATA_END - pd.Timedelta(weeks=holdout_weeks)
    s = summary_data(orders, cal_end, DATA_END)
    bg = BGNBD().fit(s["x"].values, s["t_x"].values, s["T"].values)
    s["pred_holdout"] = bg.expected_purchases(holdout_weeks, s["x"], s["t_x"], s["T"])
    # Naive baseline: each customer keeps buying at their historical rate.
    s["baseline_holdout"] = (s["x"] + 1) / np.maximum(s["T"], 1) * holdout_weeks
    metrics = {
        "calibration_end": str(cal_end.date()),
        "holdout_weeks": holdout_weeks,
        "customers": len(s),
        "actual_total": float(s["x_holdout"].sum()),
        "predicted_total": float(s["pred_holdout"].sum()),
        "baseline_total": float(s["baseline_holdout"].sum()),
        "mae_model": float((s["pred_holdout"] - s["x_holdout"]).abs().mean()),
        "mae_baseline": float((s["baseline_holdout"] - s["x_holdout"]).abs().mean()),
        "corr_model": float(np.corrcoef(s["pred_holdout"], s["x_holdout"])[0, 1]),
        "params": {"r": bg.r, "alpha": bg.alpha, "a": bg.a, "b": bg.b},
    }
    # Calibration plot data: mean actual vs predicted by number of calibration repeat purchases.
    s["x_bucket"] = s["x"].clip(upper=10)
    calib = s.groupby("x_bucket")[["x_holdout", "pred_holdout", "baseline_holdout"]].mean().reset_index()
    return calib, metrics


def predict_clv(orders: pd.DataFrame, horizon_weeks: int = 52) -> tuple[pd.DataFrame, dict]:
    s = summary_data(orders, DATA_END)
    bg = BGNBD().fit(s["x"].values, s["t_x"].values, s["T"].values)
    rep = s[(s["x"] > 0) & (s["monetary"] > 0)]
    gg = GammaGamma().fit(rep["x"].values, rep["monetary"].values)
    pop_mean = gg.p * gg.v / (gg.q - 1)
    s["p_alive"] = bg.p_alive(s["x"], s["t_x"], s["T"])
    s["exp_purchases_12m"] = bg.expected_purchases(horizon_weeks, s["x"], s["t_x"], s["T"])
    s["exp_spend"] = gg.expected_spend(s["x"].values, s["monetary"].fillna(0).values, pop_mean)
    s["clv_12m"] = (s["exp_purchases_12m"] * s["exp_spend"]).round(2)
    s["clv_decile"] = pd.qcut(s["clv_12m"].rank(method="first"), 10, labels=range(10, 0, -1)).astype(int)
    params = {"bgnbd": {"r": bg.r, "alpha": bg.alpha, "a": bg.a, "b": bg.b},
              "gamma_gamma": {"p": gg.p, "q": gg.q, "v": gg.v},
              # Independence assumption of Gamma-Gamma: frequency and spend should be uncorrelated.
              "freq_spend_corr": float(rep[["x", "monetary"]].corr().iloc[0, 1])}
    return s.reset_index(), params
