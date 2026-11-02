"""Weekly revenue forecasting, benchmarked against naive baselines on a held-out window.

Only ~2 years of weekly history exist, too short for a 52-week Holt-Winters season, so
annual seasonality is modelled with Fourier terms inside a regression / SARIMAX instead.
Models are scored with MASE (scaled by the seasonal-naive in-sample error) and MAPE.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.statespace.sarimax import SARIMAX

from retail.analysis.common import query
from retail.config import FORECAST_HOLDOUT_WEEKS

PERIOD = 52.18  # weeks per year
K = 4  # Fourier harmonic pairs


def weekly_revenue() -> pd.Series:
    df = query("select week_start, sum(gross_revenue) revenue, count(*) n_days "
               "from mart_daily_kpis group by 1 order by 1")
    df["week_start"] = pd.to_datetime(df["week_start"])
    # Drop the partial first and last weeks (data starts on a Tuesday, ends on a Friday).
    df = df[df["n_days"] == 7]
    return df.set_index("week_start")["revenue"].asfreq("W-MON")


def fourier(index: pd.DatetimeIndex, origin: pd.Timestamp) -> pd.DataFrame:
    t = ((index - origin).days / 7).to_numpy()
    cols = {"trend": t}
    for k in range(1, K + 1):
        cols[f"sin{k}"] = np.sin(2 * np.pi * k * t / PERIOD)
        cols[f"cos{k}"] = np.cos(2 * np.pi * k * t / PERIOD)
    # The shop shuts between Christmas and New Year: a dummy for that closure week.
    cols["xmas_close"] = (index.month == 12) & (index.day >= 25)
    return pd.DataFrame(cols, index=index).astype(float)


def _models(train: pd.Series, horizon_index: pd.DatetimeIndex):
    """Return {name: (point forecast, lower 80%, upper 80%)} for the horizon."""
    origin = train.index[0]
    out = {}

    # 1. Naive: last observed week repeated.
    last = np.repeat(train.iloc[-1], len(horizon_index))
    out["naive (last week)"] = (last, None, None)

    # 2. Seasonal naive: same week last year.
    snaive = np.array([train.asof(d - pd.Timedelta(weeks=52)) for d in horizon_index])
    out["seasonal naive"] = (snaive, None, None)

    # 3. Seasonal naive scaled by trailing 13-week year-over-year growth.
    recent = train.iloc[-13:].sum()
    year_ago = sum(train.asof(d - pd.Timedelta(weeks=52)) for d in train.index[-13:])
    out["seasonal naive + growth"] = (snaive * recent / year_ago, None, None)

    # 4. Regression with linear trend + Fourier seasonality + closure dummy.
    X = sm.add_constant(fourier(train.index, origin))
    ols = sm.OLS(train, X).fit()
    Xf = sm.add_constant(fourier(horizon_index, origin), has_constant="add")
    pr = ols.get_prediction(Xf).summary_frame(alpha=0.2)
    out["fourier regression"] = (pr["mean"].values, pr["obs_ci_lower"].values,
                                 pr["obs_ci_upper"].values)

    # 5. SARIMAX: ARMA(1,1) errors on top of the same exogenous seasonality.
    sar = SARIMAX(train, exog=fourier(train.index, origin), order=(1, 0, 1), trend="c").fit(
        disp=False, maxiter=500)
    fc = sar.get_forecast(len(horizon_index), exog=fourier(horizon_index, origin))
    ci = fc.conf_int(alpha=0.2)
    out["SARIMAX + fourier"] = (fc.predicted_mean.values, ci.iloc[:, 0].values, ci.iloc[:, 1].values)

    # 6. Simple average of the two structurally different good models: forecast combination.
    ens = (out["seasonal naive + growth"][0] + out["fourier regression"][0]) / 2
    out["ensemble (growth-naive + fourier)"] = (ens, None, None)
    return {k: (np.clip(v[0], 0, None), *v[1:]) for k, v in out.items()}


def _mase(actual, pred, train: pd.Series) -> float:
    scale = (train - train.shift(52)).abs().mean()
    return float(np.mean(np.abs(actual - pred)) / scale)


def run(holdout: int = FORECAST_HOLDOUT_WEEKS):
    y = weekly_revenue()
    train, test = y.iloc[:-holdout], y.iloc[-holdout:]
    rows, frames = [], []
    for name, (pred, lo, hi) in _models(train, test.index).items():
        rows.append({
            "model": name,
            "mase": _mase(test.values, pred, train),
            "mape": float(np.mean(np.abs(test.values - pred) / test.values)),
            "total_error_pct": float(pred.sum() / test.sum() - 1),
            "coverage_80": (float(np.mean((test.values >= lo) & (test.values <= hi)))
                            if lo is not None else np.nan),
        })
        frames.append(pd.DataFrame({"week_start": test.index, "model": name, "forecast": pred,
                                    "lower": lo, "upper": hi}))
    scores = pd.DataFrame(rows).sort_values("mase")
    best = scores["model"].iat[0]

    # Refit the winning model on all data and forecast the next quarter.
    future_idx = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=holdout, freq="W-MON")
    pred, lo, hi = _models(y, future_idx)[best]
    if lo is None:
        # No analytic interval for naive/ensemble models: use the empirical 80th percentile of
        # absolute percentage error on the holdout as a symmetric band.
        hb = frames[[f["model"].iat[0] for f in frames].index(best)]
        ape = np.abs(hb["forecast"].values / test.values - 1)
        q = np.quantile(ape, 0.8)
        lo, hi = pred * (1 - q), pred * (1 + q)
    future = pd.DataFrame({"week_start": future_idx, "model": best, "forecast": pred,
                           "lower": lo, "upper": hi})
    history = y.rename("revenue").reset_index()
    return history, scores, pd.concat(frames), future, best
