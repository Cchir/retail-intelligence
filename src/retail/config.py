"""Project paths and constants. Everything is relative to the repository root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"
WAREHOUSE = DATA / "warehouse"
DB_PATH = WAREHOUSE / "retail.duckdb"
SQL = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SOURCE_ZIP = RAW / "online_retail_ii.zip"
SOURCE_XLSX = RAW / "online_retail_II.xlsx"
# Parquet "bronze" copy of the spreadsheet: reading the xlsx takes minutes, parquet takes milliseconds.
BRONZE = RAW / "transactions_bronze.parquet"

SHEETS = ("Year 2009-2010", "Year 2010-2011")

# Non-product stock codes found during EDA: postage, fees, manual adjustments, bank charges, etc.
NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "C2", "D", "S", "B", "BANK CHARGES", "AMAZONFEE", "CRUK", "PADS",
    "ADJUST", "ADJUST2", "TEST001", "TEST002", "SP1002", "GIFT",
}

# Analysis windows
CHURN_HORIZON_DAYS = 90
FORECAST_HOLDOUT_WEEKS = 12


def ensure_dirs() -> None:
    for p in (RAW, WAREHOUSE, REPORTS, FIGURES):
        p.mkdir(parents=True, exist_ok=True)
