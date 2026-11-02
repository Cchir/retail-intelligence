"""Customer segmentation: rule-based RFM scores, then k-means on the log-scaled RFM space.

RFM gives business users segments they can read; k-means checks whether the data actually
supports that many groups (choose k by silhouette) and gives a data-driven alternative.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from retail.analysis.common import DATA_END


def rfm_table(orders: pd.DataFrame, as_of: pd.Timestamp = DATA_END) -> pd.DataFrame:
    g = orders[orders["date_key"] <= as_of].groupby("customer_key")
    rfm = pd.DataFrame({
        "recency_days": (as_of - g["date_key"].max()).dt.days,
        "frequency": g["invoice_no"].nunique(),
        "monetary": g["order_value"].sum().round(2),
        "tenure_days": (as_of - g["date_key"].min()).dt.days,
        "country": g["country"].agg(lambda s: s.mode().iat[0] if s.notna().any() else None),
    })
    # Quintile scores, 5 = best. Rank first so ties don't break qcut.
    rfm["r_score"] = pd.qcut(rfm["recency_days"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["segment"] = rfm.apply(_rfm_segment, axis=1)
    return rfm


def _rfm_segment(row) -> str:
    r, fm = row["r_score"], (row["f_score"] + row["m_score"]) / 2
    if r >= 4 and fm >= 4:
        return "Champions"
    if r >= 3 and fm >= 3:
        return "Loyal"
    if r >= 4 and fm < 2:
        return "New"
    if r >= 3:
        return "Promising"
    if r == 2 and fm >= 3:
        return "At risk"
    if r <= 2 and fm >= 4:
        return "Can't lose"
    if r == 2:
        return "Needs attention"
    return "Lost"


def kmeans_segments(rfm: pd.DataFrame, k_range=range(2, 9), seed: int = 42):
    X = np.column_stack([
        np.log1p(rfm["recency_days"]),
        np.log1p(rfm["frequency"]),
        np.log1p(rfm["monetary"].clip(lower=0)),
    ])
    Xs = StandardScaler().fit_transform(X)
    scores = {}
    for k in k_range:
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(Xs)
        scores[k] = silhouette_score(Xs, labels, sample_size=3000, random_state=seed)
    best_k = max(scores, key=scores.get)
    # Silhouette favours k=2 on most customer data; a 2-way split isn't actionable, so take
    # the best k >= 4 unless it is clearly worse (within 0.10 of the max).
    actionable = {k: s for k, s in scores.items() if k >= 4}
    k_ch = max(actionable, key=actionable.get)
    if scores[best_k] - actionable[k_ch] < 0.10:
        best_k = k_ch
    km = KMeans(n_clusters=best_k, n_init=10, random_state=seed).fit(Xs)
    out = rfm.copy()
    out["cluster"] = km.labels_
    # Order clusters by mean monetary value so cluster 0 is always the most valuable.
    order = out.groupby("cluster")["monetary"].mean().sort_values(ascending=False).index
    out["cluster"] = out["cluster"].map({c: i for i, c in enumerate(order)})
    return out, pd.Series(scores, name="silhouette").rename_axis("k").reset_index(), best_k


def segment_summary(seg: pd.DataFrame, by: str) -> pd.DataFrame:
    total = seg["monetary"].sum()
    return (
        seg.groupby(by)
        .agg(customers=("frequency", "size"), recency_days=("recency_days", "median"),
             frequency=("frequency", "median"), monetary=("monetary", "median"),
             revenue=("monetary", "sum"))
        .assign(revenue_share=lambda d: (d["revenue"] / total).round(4))
        .sort_values("revenue", ascending=False)
        .reset_index()
    )
