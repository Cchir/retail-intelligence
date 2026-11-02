"""Purchase propensity: will a customer buy again in the next 90 days?

Framed as a supervised problem with point-in-time features so there is no leakage:
features use only data up to a cutoff date, the label uses only the 90 days after it.
Training stacks several historical cutoffs; the test set is the most recent cutoff,
i.e. a genuine out-of-time evaluation, the way the model would be used in production.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from retail.analysis.common import DATA_END
from retail.config import CHURN_HORIZON_DAYS

FEATURES = [
    "recency_days", "tenure_days", "n_orders", "revenue", "avg_order_value",
    "orders_90d", "revenue_90d", "orders_365d", "mean_gap_days", "days_since_expected",
    "distinct_months", "is_uk",
]


def features_at(orders: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    hist = orders[orders["date_key"] <= cutoff]
    g = hist.groupby("customer_key")
    f = pd.DataFrame({
        "recency_days": (cutoff - g["date_key"].max()).dt.days,
        "tenure_days": (cutoff - g["date_key"].min()).dt.days,
        "n_orders": g["invoice_no"].nunique(),
        "revenue": g["order_value"].sum(),
        "distinct_months": g["date_key"].apply(lambda s: s.dt.to_period("M").nunique()),
        "is_uk": g["country"].agg(lambda s: (s == "United Kingdom").mean() > 0.5).astype(int),
    })
    f["avg_order_value"] = f["revenue"] / f["n_orders"]
    for days in (90, 365):
        recent = hist[hist["date_key"] > cutoff - pd.Timedelta(days=days)].groupby("customer_key")
        f[f"orders_{days}d"] = recent["invoice_no"].nunique().reindex(f.index, fill_value=0)
        if days == 90:
            f["revenue_90d"] = recent["order_value"].sum().reindex(f.index, fill_value=0)
    f["mean_gap_days"] = np.where(f["n_orders"] > 1, f["tenure_days"] / (f["n_orders"] - 1), np.nan)
    # How overdue is the customer relative to their own buying rhythm? (NaN for one-off buyers)
    f["days_since_expected"] = f["recency_days"] - f["mean_gap_days"]

    future = orders[(orders["date_key"] > cutoff)
                    & (orders["date_key"] <= cutoff + pd.Timedelta(days=CHURN_HORIZON_DAYS))]
    f["label"] = f.index.isin(future["customer_key"]).astype(int)
    f["cutoff"] = cutoff
    return f


def build_dataset(orders: pd.DataFrame):
    test_cutoff = DATA_END - pd.Timedelta(days=CHURN_HORIZON_DAYS)
    # Quarterly cutoffs going back; each label window ends before the test cutoff.
    train_cutoffs = [test_cutoff - pd.Timedelta(days=CHURN_HORIZON_DAYS * k) for k in range(1, 5)]
    train = pd.concat([features_at(orders, c) for c in train_cutoffs])
    test = features_at(orders, test_cutoff)
    return train, test


def _lift_at(y, p, frac=0.1):
    n = max(1, int(len(p) * frac))
    top = np.argsort(-p)[:n]
    return float(y[top].mean() / y.mean())


def run(orders: pd.DataFrame, seed: int = 42):
    train, test = build_dataset(orders)
    Xtr, ytr = train[FEATURES], train["label"].values
    Xte, yte = test[FEATURES], test["label"].values

    models = {
        # Baseline a business would use without a model: rank by recency alone.
        "recency rule": None,
        "logistic regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, C=0.5)),
        "gradient boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
            random_state=seed),
    }
    # Log-transform skewed money/count features for the linear model; trees don't care.
    log_cols = ["revenue", "avg_order_value", "revenue_90d", "n_orders", "orders_365d", "tenure_days"]

    def prep_linear(X):
        X = X.copy()
        X[log_cols] = np.log1p(X[log_cols].clip(lower=0))
        return X.fillna(X.median())

    results, scores, curves = [], {}, []
    for name, model in models.items():
        if model is None:
            p = 1.0 / (1.0 + test["recency_days"].values)
        elif name == "logistic regression":
            model.fit(prep_linear(Xtr), ytr)
            p = model.predict_proba(prep_linear(Xte))[:, 1]
        else:
            model.fit(Xtr, ytr)
            p = model.predict_proba(Xte)[:, 1]
        scores[name] = p
        results.append({
            "model": name,
            "roc_auc": roc_auc_score(yte, p),
            "pr_auc": average_precision_score(yte, p),
            "brier": brier_score_loss(yte, p) if model is not None else np.nan,
            "lift_top_decile": _lift_at(yte, p),
        })
        fpr, tpr, _ = roc_curve(yte, p)
        idx = np.linspace(0, len(fpr) - 1, 200).astype(int)
        curves.append(pd.DataFrame({"model": name, "fpr": fpr[idx], "tpr": tpr[idx]}))

    gb = models["gradient boosting"]
    imp = permutation_importance(gb, Xte, yte, scoring="roc_auc", n_repeats=10, random_state=seed)
    importance = (pd.DataFrame({"feature": FEATURES, "importance": imp.importances_mean,
                                "std": imp.importances_std})
                  .sort_values("importance", ascending=False))
    frac_pos, mean_pred = calibration_curve(yte, scores["gradient boosting"], n_bins=10,
                                            strategy="quantile")
    calibration = pd.DataFrame({"mean_predicted": mean_pred, "fraction_positive": frac_pos})

    scored = test[["recency_days", "n_orders", "revenue"]].copy()
    scored["p_purchase_90d"] = scores["gradient boosting"]
    scored["actual"] = yte
    meta = {
        "train_rows": len(train), "test_rows": len(test),
        "train_cutoffs": [str(c.date()) for c in sorted(train["cutoff"].unique())],
        "test_cutoff": str(test["cutoff"].iat[0].date()),
        "base_rate_test": float(yte.mean()),
    }
    return (pd.DataFrame(results), pd.concat(curves), importance, calibration,
            scored.reset_index(), meta)
