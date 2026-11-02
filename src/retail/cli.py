"""Command-line entry point.

    retail build       # extract -> transform -> load -> quality checks
    retail analyse     # statistical analysis and models, writes data/warehouse + reports
    retail export      # write dashboard-facing tables to dashboard/data
    retail all         # build + analyse + export
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from retail import config, export, extract, load, quality, transform


def build(force: bool = False) -> None:
    log = logging.getLogger("retail.build")
    t0 = time.perf_counter()
    bronze = extract.run(force=force)
    log.info("extract: %s rows", f"{len(bronze):,}")
    silver = transform.run(bronze)
    log.info("transform: %s", silver["row_status"].value_counts().to_dict())
    load.run(silver)
    con = load.connect()
    try:
        checks = quality.run(con)
    finally:
        con.close()
    for c in checks:
        mark = "PASS" if c.passed else ("FAIL" if c.severity == "error" else "WARN")
        log.info("[%s] %s (%s)", mark, c.name, c.failures)
    failed = [c for c in checks if not c.passed and c.severity == "error"]
    if failed:
        log.error("%d quality check(s) failed", len(failed))
        sys.exit(1)
    log.info("build finished in %.1fs", time.perf_counter() - t0)


def analyse() -> None:
    from retail.analysis import run_all

    run_all.run()


def main() -> None:
    parser = argparse.ArgumentParser(prog="retail")
    parser.add_argument("command", choices=["build", "analyse", "export", "all"])
    parser.add_argument("--force", action="store_true", help="re-download and rebuild bronze")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s | %(message)s")
    config.ensure_dirs()
    if args.command in ("build", "all"):
        build(force=args.force)
    if args.command in ("analyse", "all"):
        analyse()
    if args.command in ("export", "all"):
        export.run()


if __name__ == "__main__":
    main()
