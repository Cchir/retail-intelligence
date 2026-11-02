"""Load: write the silver table into DuckDB and build the SQL models (staging -> marts)."""

from __future__ import annotations

import logging

import duckdb
import pandas as pd

from retail import config

log = logging.getLogger(__name__)


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    config.ensure_dirs()
    return duckdb.connect(str(config.DB_PATH), read_only=read_only)


def model_files() -> list:
    return sorted(config.SQL.glob("staging/*.sql")) + sorted(config.SQL.glob("marts/*.sql"))


def run(silver: pd.DataFrame) -> None:
    con = connect()
    try:
        con.register("silver_df", silver)
        con.execute("create or replace table silver_transactions as select * from silver_df")
        con.unregister("silver_df")
        for path in model_files():
            log.info("model %s", path.relative_to(config.SQL))
            con.execute(path.read_text(encoding="utf-8"))
    finally:
        con.close()
