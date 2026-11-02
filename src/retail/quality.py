"""Data quality checks, run after every build. A failed `error` check stops the pipeline.

Each check is a SQL query returning a single number of offending rows (0 = pass), in the
spirit of dbt tests, so a reviewer can paste any of them straight into DuckDB.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from retail import config


@dataclass
class Check:
    name: str
    sql: str
    severity: str = "error"  # or "warn"
    failures: int | None = None

    @property
    def passed(self) -> bool:
        return self.failures == 0


CHECKS = [
    Check("row count reconciles bronze -> silver",
          f"select abs((select count(*) from '{config.BRONZE.as_posix()}')"
          " - (select count(*) from silver_transactions))"),
    Check("every silver row has a status",
          "select count(*) from silver_transactions where row_status is null"),
    Check("fct_sales: quantity and price strictly positive",
          "select count(*) from fct_sales where quantity <= 0 or unit_price <= 0"),
    Check("fct_returns: only cancellation invoices",
          "select count(*) from fct_returns where invoice_no not like 'C%'"),
    Check("fct_orders: invoice_no unique",
          "select count(*) - count(distinct invoice_no) from fct_orders"),
    Check("dim_customer: key unique",
          "select count(*) - count(distinct customer_key) from dim_customer"),
    Check("dim_product: key unique",
          "select count(*) - count(distinct product_key) from dim_product"),
    Check("fct_sales -> dim_product referential integrity",
          "select count(*) from fct_sales s anti join dim_product p on s.product_key = p.product_key"),
    Check("fct_sales -> dim_customer referential integrity",
          "select count(*) from fct_sales s anti join dim_customer c on s.customer_key = c.customer_key"
          " where s.customer_key is not null"),
    Check("fct_sales -> dim_date referential integrity",
          "select count(*) from fct_sales s anti join dim_date d on s.date_key = d.date_key"),
    Check("revenue reconciles fct_sales = fct_orders",
          "select (abs((select sum(line_revenue) from fct_sales)"
          " - (select sum(order_value) from fct_orders)) > 1)::int"),
    Check("daily KPI has no calendar gaps",
          "select (select count(*) from dim_date) - (select count(*) from mart_daily_kpis)"),
    Check("cohort retention within [0, 1]",
          "select count(*) from mart_cohort_retention where retention < 0 or retention > 1"),
    Check("guest share of sale lines below 30%",
          "select ((select avg(is_guest::int) from fct_sales) > 0.30)::int", "warn"),
    Check("no single day above 5x the median daily revenue",
          "select count(*) from mart_daily_kpis where gross_revenue >"
          " 5 * (select median(gross_revenue) from mart_daily_kpis where orders > 0)", "warn"),
]


def run(con) -> list[Check]:
    for c in CHECKS:
        c.failures = int(con.execute(c.sql).fetchone()[0])
    status = con.execute(
        "select row_status, count(*) n, round(sum(line_revenue), 2) revenue "
        "from silver_transactions group by 1 order by n desc"
    ).df()
    report = {
        # Report paths relative to the repo so the published report doesn't carry local paths.
        "checks": [asdict(c) | {"sql": c.sql.replace(config.ROOT.as_posix(), "."), "passed": c.passed}
                   for c in CHECKS],
        "row_status": status.to_dict(orient="records"),
    }
    (config.REPORTS / "data_quality.json").write_text(json.dumps(report, indent=2, default=str))
    return CHECKS
