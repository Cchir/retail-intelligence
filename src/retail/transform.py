"""Transform: bronze -> silver.

Every row from bronze is kept and tagged with a `row_status`, rather than silently dropped.
Downstream models filter on status, and the quality report counts every exclusion reason,
so the path from 1,067,371 source rows to the analysed set is fully accounted for.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from retail import config

# Order matters: a row gets the first status that applies.
STATUSES = (
    "duplicate",
    "test_or_adjustment",
    "non_product",
    "zero_or_negative_price",
    "cancellation",
    "stock_adjustment",
    "valid_sale",
)


def standardise(bronze: pd.DataFrame) -> pd.DataFrame:
    df = bronze.rename(
        columns={
            "Invoice": "invoice_no",
            "StockCode": "stock_code",
            "Description": "description",
            "Quantity": "quantity",
            "InvoiceDate": "invoice_ts",
            "Price": "unit_price",
            "Customer ID": "customer_id",
            "Country": "country",
        }
    ).copy()
    df["invoice_no"] = df["invoice_no"].str.strip()
    df["stock_code"] = df["stock_code"].str.strip().str.upper()
    df["description"] = (
        df["description"].str.strip().str.upper().str.replace(r"\s+", " ", regex=True)
    )
    df["customer_id"] = df["customer_id"].astype("Int64")
    # The source uses both "EIRE" and "Ireland"-style variants and an "Unspecified" bucket.
    df["country"] = (
        df["country"]
        .str.strip()
        .replace({"EIRE": "Ireland", "RSA": "South Africa", "Unspecified": pd.NA})
    )
    df["line_revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["is_cancellation"] = df["invoice_no"].str.startswith("C")
    return df


def classify(df: pd.DataFrame) -> pd.DataFrame:
    key = ["invoice_no", "stock_code", "description", "quantity", "invoice_ts",
           "unit_price", "customer_id", "country"]
    is_dup = df.duplicated(subset=key, keep="first")
    code = df["stock_code"]
    is_test = code.str.startswith(("TEST", "ADJUST")) | df["invoice_no"].str.startswith("A")
    is_non_product = code.isin(config.NON_PRODUCT_CODES) | code.str.startswith(("GIFT", "DCGS"))
    is_bad_price = df["unit_price"] <= 0
    is_cancel = df["is_cancellation"]
    # Negative quantity on a normal invoice with no customer = warehouse write-off ("damaged", "?").
    is_stock_adj = (df["quantity"] < 0) & ~is_cancel

    conditions = [is_dup, is_test, is_non_product, is_bad_price, is_cancel, is_stock_adj]
    df["row_status"] = np.select(conditions, STATUSES[:-1], default="valid_sale")
    return df


def canonical_descriptions(df: pd.DataFrame) -> pd.Series:
    """A stock code has up to 9 spellings over two years: keep the most frequent one."""
    valid = df[df["row_status"] == "valid_sale"].dropna(subset=["description"])
    return (
        valid.groupby(["stock_code", "description"]).size()
        .sort_values(ascending=False)
        .reset_index()
        .drop_duplicates("stock_code")
        .set_index("stock_code")["description"]
    )


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Flag (don't drop) extreme lines. Robust z-score of log line revenue per stock code.

    The famous 80,995-unit order (and its immediate cancellation) is exactly this kind of row.
    """
    sale = df["row_status"] == "valid_sale"
    log_rev = np.log1p(df.loc[sale, "line_revenue"])
    grp = log_rev.groupby(df.loc[sale, "stock_code"])
    med = grp.transform("median")
    mad = grp.transform(lambda s: (s - s.median()).abs().median()).replace(0, np.nan)
    robust_z = 0.6745 * (log_rev - med) / mad
    df["is_outlier"] = False
    df.loc[sale, "is_outlier"] = (robust_z > 6).fillna(False) & (df.loc[sale, "line_revenue"] > 1_000)
    # Products sold only once have no spread to compare against: fall back to an absolute cap.
    df.loc[sale & (df["quantity"] >= 10_000), "is_outlier"] = True
    return df


def run(bronze: pd.DataFrame) -> pd.DataFrame:
    df = classify(standardise(bronze))
    names = canonical_descriptions(df)
    df["product_name"] = df["stock_code"].map(names).astype("string").fillna(df["description"])
    df = flag_outliers(df)
    df["invoice_date"] = df["invoice_ts"].dt.normalize()
    return df
