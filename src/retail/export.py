"""Serving layer: export the small, dashboard-facing tables to parquet.

The warehouse is ~66 MB and rebuilt from source; the dashboard only needs aggregated marts and
model outputs (a few MB), which are committed so the app deploys without running the pipeline.
"""

from __future__ import annotations

import logging
import shutil

from retail import config, load

log = logging.getLogger(__name__)

SERVING = config.ROOT / "dashboard" / "data"

TABLES = [
    "dim_customer", "dim_product", "fct_orders", "mart_daily_kpis", "mart_cohort_retention",
    "mart_country",
]


def run() -> None:
    if SERVING.exists():
        shutil.rmtree(SERVING)
    SERVING.mkdir(parents=True)
    con = load.connect(read_only=True)
    try:
        analytics = [r[0] for r in con.execute(
            "select table_name from information_schema.tables where table_schema = 'analytics'"
        ).fetchall()]
        for t in TABLES + [f"analytics.{a}" for a in analytics]:
            out = SERVING / f"{t.removeprefix('analytics.')}.parquet"
            con.execute(f"copy (select * from {t}) to '{out.as_posix()}' (format parquet, compression zstd)")
        status = SERVING / "row_status.parquet"
        con.execute(
            "copy (select row_status, count(*) n_rows, round(sum(line_revenue), 2) revenue "
            f"from silver_transactions group by 1 order by 2 desc) to '{status.as_posix()}' (format parquet)"
        )
    finally:
        con.close()
    for f in ("data_quality.json", "metrics.json"):
        shutil.copy(config.REPORTS / f, SERVING / f)
    size = sum(p.stat().st_size for p in SERVING.iterdir()) / 1e6
    log.info("exported %d files (%.1f MB) to %s", len(list(SERVING.iterdir())), size, SERVING)
