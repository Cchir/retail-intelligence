"""Shared helpers for the analysis modules."""

from __future__ import annotations

import pandas as pd

from retail import load

# Last full day in the data; all "as of" analysis is relative to this.
DATA_END = pd.Timestamp("2011-12-09")


def query(sql: str, **params) -> pd.DataFrame:
    con = load.connect(read_only=True)
    try:
        return con.execute(sql, params or None).df()
    finally:
        con.close()


def customer_orders() -> pd.DataFrame:
    """One row per identified customer per order, outlier orders removed."""
    df = query(
        """
        select customer_key, invoice_no, date_key, order_value, n_lines, units, country
        from fct_orders
        where customer_key is not null and not has_outlier
        """
    )
    df["date_key"] = pd.to_datetime(df["date_key"])
    return df


def write_table(name: str, df: pd.DataFrame) -> None:
    """Persist an analysis output into the warehouse `analytics` schema for the dashboard."""
    con = load.connect()
    try:
        con.execute("create schema if not exists analytics")
        con.register("_df", df)
        con.execute(f"create or replace table analytics.{name} as select * from _df")
        con.unregister("_df")
    finally:
        con.close()
