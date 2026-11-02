"""Extract: download the source archive and land it as an untouched "bronze" parquet file.

The bronze layer keeps every source row and column exactly as published (plus lineage columns),
so any downstream cleaning decision can be audited and re-run without touching the network.
"""

from __future__ import annotations

import hashlib
import logging
import zipfile
from datetime import UTC, datetime

import pandas as pd
import requests

from retail import config

log = logging.getLogger(__name__)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(force: bool = False) -> None:
    config.ensure_dirs()
    if config.SOURCE_ZIP.exists() and not force:
        log.info("source archive already present (%s)", config.SOURCE_ZIP.name)
    else:
        log.info("downloading %s", config.SOURCE_URL)
        with requests.get(config.SOURCE_URL, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(config.SOURCE_ZIP, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    log.info("sha256 %s", _sha256(config.SOURCE_ZIP))
    if not config.SOURCE_XLSX.exists() or force:
        with zipfile.ZipFile(config.SOURCE_ZIP) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
            with z.open(member) as src, open(config.SOURCE_XLSX, "wb") as dst:
                dst.write(src.read())


def to_bronze(force: bool = False) -> pd.DataFrame:
    """Read both workbook sheets as strings-where-ambiguous and persist to parquet."""
    if config.BRONZE.exists() and not force:
        return pd.read_parquet(config.BRONZE)

    frames = []
    for sheet in config.SHEETS:
        log.info("reading sheet %r (slow: openpyxl)", sheet)
        # Invoice and StockCode mix numbers and letters ("C489449", "85123A"): force text.
        df = pd.read_excel(
            config.SOURCE_XLSX,
            sheet_name=sheet,
            dtype={"Invoice": str, "StockCode": str, "Description": str, "Country": str},
            engine="openpyxl",
        )
        df["_source_sheet"] = sheet
        df["_source_row"] = range(2, len(df) + 2)  # spreadsheet row number, header is row 1
        frames.append(df)

    bronze = pd.concat(frames, ignore_index=True)
    bronze["_ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
    bronze.to_parquet(config.BRONZE, index=False)
    log.info("bronze rows: %s", f"{len(bronze):,}")
    return bronze


def run(force: bool = False) -> pd.DataFrame:
    download(force=force)
    return to_bronze(force=force)
