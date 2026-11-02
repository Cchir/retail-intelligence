"""Run every analysis, persist results to the warehouse `analytics` schema and reports/metrics.json."""

from __future__ import annotations

import json
import logging
import time

import numpy as np

from retail import config
from retail.analysis import churn, clv, forecast, segmentation, stats_tests
from retail.analysis.common import customer_orders, write_table

log = logging.getLogger("retail.analyse")


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_jsonable(v) for v in o]
    return o


def run() -> dict:
    t0 = time.perf_counter()
    orders = customer_orders()
    metrics: dict = {}

    log.info("segmentation")
    rfm = segmentation.rfm_table(orders)
    seg, silhouette, k = segmentation.kmeans_segments(rfm)
    write_table("customer_segments", seg.reset_index())
    write_table("segment_summary", segmentation.segment_summary(seg, "segment"))
    write_table("cluster_summary", segmentation.segment_summary(seg, "cluster"))
    write_table("kmeans_silhouette", silhouette)
    metrics["segmentation"] = {"k": k, "silhouette": silhouette.set_index("k")["silhouette"].round(3).to_dict()}

    log.info("customer lifetime value (BG/NBD + Gamma-Gamma)")
    calib, clv_val = clv.validate(orders)
    clv_df, clv_params = clv.predict_clv(orders)
    write_table("clv_calibration", calib)
    write_table("customer_clv", clv_df)
    metrics["clv"] = {"validation": clv_val, "params": clv_params,
                      "total_12m": float(clv_df["clv_12m"].sum()),
                      "top_decile_share": float(clv_df.loc[clv_df["clv_decile"] == 1, "clv_12m"].sum()
                                                / clv_df["clv_12m"].sum())}

    log.info("purchase propensity")
    res, curves, imp, cal, scored, meta = churn.run(orders)
    for name, df in [("propensity_scores", res), ("propensity_roc", curves),
                     ("propensity_importance", imp), ("propensity_calibration", cal),
                     ("propensity_test_scored", scored)]:
        write_table(name, df)
    metrics["propensity"] = {"meta": meta, "results": res.round(4).to_dict(orient="records")}

    log.info("forecasting")
    history, scores, backtest, future, best = forecast.run()
    write_table("weekly_revenue", history)
    write_table("forecast_scores", scores)
    write_table("forecast_backtest", backtest)
    write_table("forecast_future", future)
    metrics["forecast"] = {"best_model": best, "scores": scores.round(4).to_dict(orient="records"),
                           "next_12_weeks": float(future["forecast"].sum())}

    log.info("hypothesis tests and market basket")
    tests = stats_tests.run(orders)
    write_table("hypothesis_tests", tests)
    write_table("market_basket", stats_tests.market_basket())
    metrics["hypothesis_tests"] = tests.to_dict(orient="records")

    (config.REPORTS / "metrics.json").write_text(json.dumps(_jsonable(metrics), indent=2, default=str))
    log.info("analysis finished in %.1fs", time.perf_counter() - t0)
    return metrics
