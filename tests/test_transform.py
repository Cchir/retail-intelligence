"""Unit tests for the cleaning rules, on small hand-built frames shaped like the source."""

import pandas as pd
import pytest

from retail import transform


def bronze(rows):
    cols = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price",
            "Customer ID", "Country"]
    df = pd.DataFrame(rows, columns=cols)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    return df


TS = "2011-01-05 10:00"


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (["536365", "85123A", "WHITE HEART", 6, TS, 2.55, 17850.0, "United Kingdom"], "valid_sale"),
        (["C536379", "85123A", "WHITE HEART", -1, TS, 2.55, 17850.0, "United Kingdom"], "cancellation"),
        (["536370", "POST", "POSTAGE", 3, TS, 18.0, 12583.0, "France"], "non_product"),
        (["536370", "GIFT_0001_20", "VOUCHER", 1, TS, 20.0, None, "United Kingdom"], "non_product"),
        (["A563185", "B", "Adjust bad debt", 1, TS, 11062.06, None, "United Kingdom"], "test_or_adjustment"),
        (["536414", "22139", None, 56, TS, 0.0, None, "United Kingdom"], "zero_or_negative_price"),
        (["536589", "21777", "DAMAGED", -10, TS, 1.25, None, "United Kingdom"], "stock_adjustment"),
    ],
)
def test_row_status(row, expected):
    out = transform.run(bronze([row]))
    assert out["row_status"].iat[0] == expected


def test_exact_duplicate_keeps_first():
    row = ["536365", "85123A", "WHITE HEART", 6, TS, 2.55, 17850.0, "United Kingdom"]
    out = transform.run(bronze([row, row]))
    assert out["row_status"].tolist() == ["valid_sale", "duplicate"]


def test_no_rows_dropped():
    rows = [["536365", "85123A", "X", 6, TS, 2.55, 1.0, "UK"]] * 3 + \
           [["C1", "85123A", "X", -6, TS, 2.55, 1.0, "UK"]]
    assert len(transform.run(bronze(rows))) == 4


def test_standardisation():
    out = transform.run(bronze([[" 536365 ", "85123a", "  white   heart ", 2, TS, 1.5, 1.0, "EIRE"]]))
    r = out.iloc[0]
    assert (r.invoice_no, r.stock_code, r.description, r.country) == ("536365", "85123A", "WHITE HEART", "Ireland")
    assert r.line_revenue == 3.0
    assert r.invoice_date == pd.Timestamp("2011-01-05")


def test_canonical_name_is_most_frequent_spelling():
    rows = [["1", "20713", "JUMBO BAG OWLS", 1, TS, 2.0, 1.0, "UK"]] * 3 + \
           [["2", "20713", "wrongly marked", 1, TS, 2.0, 1.0, "UK"]]
    out = transform.run(bronze(rows))
    assert set(out["product_name"]) == {"JUMBO BAG OWLS"}


def test_huge_single_order_flagged_as_outlier():
    rows = [["581483", "23843", "PAPER CRAFT , LITTLE BIRDIE", 80995, TS, 2.08, 16446.0, "United Kingdom"]]
    assert transform.run(bronze(rows))["is_outlier"].iat[0]
