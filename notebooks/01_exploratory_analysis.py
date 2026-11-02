# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 01 — Exploratory data analysis: Online Retail II
#
# **Source:** [UCI Machine Learning Repository #502](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
# — every transaction of a UK-based online giftware wholesaler between 1 Dec 2009 and 9 Dec 2011.
# Many customers are themselves small retailers.
#
# **Goal of this notebook:** understand the raw data well enough to make (and justify) the cleaning
# rules used in the ETL, then get a first read on the business: how revenue moves through the year,
# who the customers are and how concentrated value is.
#
# The data is read straight from the DuckDB warehouse built by `retail build`.

# %%
import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from retail import config

con = duckdb.connect(str(config.DB_PATH), read_only=True)
q = lambda sql: con.execute(sql).df()  # noqa: E731

COBALT, AMBER, TEAL, GREY = "#5A6CF0", "#E39B2D", "#2BB39E", "#8A93A3"
sns.set_theme(style="whitegrid", font_scale=0.95)
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12})
gbp = mtick.FuncFormatter(lambda x, _: f"£{x/1e3:,.0f}k" if abs(x) >= 1e3 else f"£{x:,.0f}")


def save(fig, name):
    fig.savefig(config.FIGURES / f"{name}.png", bbox_inches="tight", dpi=150)

# %% [markdown]
# ## 1. First look at the raw (bronze) data
# Eight source columns, two spreadsheet tabs, just over a million rows.

# %%
raw = q(f"select * from '{config.BRONZE.as_posix()}'")
print(f"{len(raw):,} rows x {raw.shape[1]} columns")
raw.drop(columns=["_ingested_at"]).head()

# %%
profile = pd.DataFrame({
    "dtype": raw.dtypes.astype(str),
    "missing": raw.isna().sum(),
    "missing_%": (raw.isna().mean() * 100).round(2),
    "distinct": raw.nunique(),
}).drop(index=["_ingested_at", "_source_row"])
profile

# %% [markdown]
# **What stands out**
#
# * **22.8 % of lines have no `Customer ID`.** These are real sales (guest checkouts) — they belong in
#   revenue figures but can't be used for customer-level modelling.
# * `Invoice` is text: a leading `C` marks a **cancellation** (credit note), `A` marks a bad-debt adjustment.
# * `Quantity` ranges from −80,995 to +80,995: one huge order that was cancelled the same day.

# %%
num = raw[["Quantity", "Price"]].describe(percentiles=[.01, .05, .5, .95, .99]).T
num

# %% [markdown]
# ## 2. Data quality issues found, and the rule used for each
#
# Each finding below became a rule in `src/retail/transform.py`. Rows are **tagged, not deleted**,
# so the funnel from raw to analysed data stays auditable.

# %%
issues = q("""
select 'exact duplicate lines' issue, count(*) - count(distinct (Invoice, StockCode, Description,
       Quantity, InvoiceDate, Price, "Customer ID", Country)) n from b
union all select 'cancellation lines (invoice starts with C)', count(*) from b where Invoice like 'C%'
union all select 'zero or negative unit price', count(*) from b where Price <= 0
union all select 'negative qty on a non-cancelled invoice', count(*) from b where Quantity < 0 and Invoice not like 'C%'
union all select 'missing description', count(*) from b where Description is null
union all select 'missing customer id', count(*) from b where "Customer ID" is null
union all select 'non-product stock codes (postage, fees, manual)', count(*) from b
          where StockCode in ('POST','DOT','M','C2','D','S','B','BANK CHARGES','AMAZONFEE','CRUK','PADS')
""".replace(" from b", f" from '{config.BRONZE.as_posix()}'"))
issues

# %%
# Stock codes carry several spellings of the same product over two years.
q(f"""select StockCode, count(distinct Description) spellings, list(distinct Description)[:4] examples
from '{config.BRONZE.as_posix()}' group by 1 order by 2 desc limit 5""")

# %% [markdown]
# ### The cleaning funnel
# The order of the rules matters (a duplicated cancellation counts once, as a duplicate).

# %%
funnel = q("""select row_status, count(*) n_rows, round(sum(line_revenue), 0) revenue
              from silver_transactions group by 1 order by n_rows desc""")
funnel["share"] = (funnel["n_rows"] / funnel["n_rows"].sum()).map("{:.2%}".format)
funnel

# %%
fig, ax = plt.subplots(figsize=(8, 3.2))
f = funnel.sort_values("n_rows")
colors = [COBALT if s == "valid_sale" else AMBER for s in f["row_status"]]
ax.barh(f["row_status"], f["n_rows"], color=colors)
ax.set_xscale("log")
ax.set_title("Every raw row is accounted for: status after cleaning (log scale)")
ax.set_xlabel("rows")
for y, v in enumerate(f["n_rows"]):
    ax.text(v * 1.1, y, f"{v:,}", va="center", fontsize=9)
save(fig, "eda_cleaning_funnel")

# %% [markdown]
# ## 3. Revenue over time
# Weekly gross revenue (outlier orders excluded). Two complete peak seasons are visible.

# %%
daily = q("select * from mart_daily_kpis order by date_key")
daily["date_key"] = pd.to_datetime(daily["date_key"])
weekly = daily.set_index("date_key")[["gross_revenue", "returns_value", "orders"]].resample("W-MON", label="left", closed="left").sum()

fig, ax = plt.subplots(figsize=(11, 3.8))
ax.plot(weekly.index, weekly["gross_revenue"], color=COBALT, lw=2, label="gross revenue")
ax.plot(weekly.index, -weekly["returns_value"], color=AMBER, lw=1.5, label="returns (credit notes)")
ax.yaxis.set_major_formatter(gbp)
ax.set_title("Weekly revenue: strong Q4 peak, flat-ish year-over-year")
ax.legend(frameon=False)
save(fig, "eda_weekly_revenue")

# %%
monthly = q("""select year, month, sum(gross_revenue) revenue from mart_daily_kpis
               group by 1, 2 order by 1, 2""")
pivot = monthly.pivot(index="month", columns="year", values="revenue")
fig, ax = plt.subplots(figsize=(9, 3.6))
for yr, c in zip([2010, 2011], [GREY, COBALT], strict=True):
    ax.plot(pivot.index, pivot[yr], marker="o", color=c, lw=2, label=str(yr))
ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
ax.yaxis.set_major_formatter(gbp)
ax.set_title("Monthly revenue, 2010 vs 2011 (Dec 2011 is a partial month)")
ax.legend(frameon=False)
save(fig, "eda_monthly_yoy")

# %% [markdown]
# ### When do orders happen?

# %%
hours = q("""select dayofweek(invoice_ts) dow, hour(invoice_ts) hr, count(distinct invoice_no) orders
             from fct_sales group by 1, 2""")
hm = hours.pivot(index="dow", columns="hr", values="orders").fillna(0)
hm.index = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][: len(hm)] if len(hm) == 7 else \
    [["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][i] for i in hm.index]
fig, ax = plt.subplots(figsize=(10, 3.2))
sns.heatmap(hm, cmap="Blues", ax=ax, cbar_kws={"label": "orders"})
ax.set_title("Orders by weekday and hour: a B2B pattern (office hours, almost no Saturdays)")
ax.set_xlabel("hour of day")
ax.set_ylabel("")
save(fig, "eda_weekday_hour")

# %% [markdown]
# ## 4. Orders and customers

# %%
orders = q("select * from fct_orders where not has_outlier")
fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
sns.histplot(np.log10(orders["order_value"]), bins=60, color=COBALT, ax=axes[0])
axes[0].set_xticks([1, 2, 3, 4], ["£10", "£100", "£1k", "£10k"])
axes[0].set_title("Order value is log-normal-ish (median £%.0f)" % orders["order_value"].median())
axes[0].set_xlabel("order value (log scale)")
sns.histplot(orders["n_lines"].clip(upper=100), bins=50, color=TEAL, ax=axes[1])
axes[1].set_title("Lines per order (capped at 100)")
save(fig, "eda_order_distributions")

# %%
guest = orders.groupby("is_guest")["order_value"].agg(["count", "sum", "median"])
guest.index = guest.index.map({False: "identified customer", True: "guest checkout"})
guest

# %%
countries = q("select * from mart_country limit 12")
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.barh(countries["country"][::-1], countries["revenue"][::-1], color=[GREY] * 11 + [COBALT])
ax.set_xscale("log")
ax.xaxis.set_major_formatter(gbp)
ax.set_title("Revenue by country (log scale): the UK is ~85% of revenue")
save(fig, "eda_countries")

# %% [markdown]
# ### How concentrated is customer value?
# A Lorenz curve: the share of revenue owned by the top x% of customers.

# %%
cust = q("select gross_revenue from dim_customer order by gross_revenue desc")["gross_revenue"].clip(lower=0)
share = cust.cumsum() / cust.sum()
pct = np.arange(1, len(cust) + 1) / len(cust)
gini = 1 - 2 * np.trapezoid(np.sort(cust).cumsum() / cust.sum(), dx=1 / len(cust))
top10 = share.iloc[int(len(cust) * 0.1)]

fig, ax = plt.subplots(figsize=(5.5, 4.2))
ax.plot(pct, share, color=COBALT, lw=2.2)
ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1)
ax.axvline(0.1, color=AMBER, lw=1)
ax.annotate(f"top 10% of customers\n= {top10:.0%} of revenue", (0.1, top10), (0.25, 0.55),
            arrowprops={"arrowstyle": "->", "color": AMBER})
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1))
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
ax.set_title(f"Customer revenue concentration (Gini = {gini:.2f})")
ax.set_xlabel("customers, ranked by revenue")
ax.set_ylabel("cumulative revenue")
save(fig, "eda_lorenz")

# %% [markdown]
# ### Retention by acquisition cohort

# %%
coh = q("select * from mart_cohort_retention where months_since_first <= 12")
grid = coh.pivot(index="cohort", columns="months_since_first", values="retention")
fig, ax = plt.subplots(figsize=(11, 7))
sns.heatmap(grid, annot=True, fmt=".0%", cmap="Blues", ax=ax, cbar=False, annot_kws={"size": 7})
ax.set_title("Share of each monthly cohort still buying N months later")
ax.set_xlabel("months since first purchase")
save(fig, "eda_cohorts")

# %% [markdown]
# * The **Dec 2009 cohort is unusually loyal** (~35–50% active each month), but that's an artefact:
#   the data starts on 1 Dec 2009, so "first seen in Dec 2009" includes years of existing customers.
#   Later cohorts are the true picture: **15–30% month-1 retention**, settling to roughly 10–20%.
# * Month 12 often bumps up: customers coming back for the next gift season.

# %% [markdown]
# ## 5. Products

# %%
prod = q("select * from dim_product order by gross_revenue desc")
prod["cum_share"] = prod["gross_revenue"].cumsum() / prod["gross_revenue"].sum()
n80 = (prod["cum_share"] < 0.8).sum() + 1
print(f"{n80:,} of {len(prod):,} products ({n80/len(prod):.0%}) make up 80% of revenue")
prod.head(10)[["product_name", "units_sold", "n_orders", "gross_revenue"]]

# %% [markdown]
# ## Summary
#
# | Finding | Consequence for the rest of the project |
# |---|---|
# | 23% of lines are guest checkouts | Revenue facts keep them; customer models use identified customers only |
# | 34k exact duplicate lines, ~18k cancellation lines, fees and postage mixed with products | Rule-based status tagging in the ETL; returns modelled as a separate fact |
# | A few huge, cancelled orders (80,995 units) distort totals | Outlier flag (robust z-score per product + absolute cap) |
# | Strong Q4 seasonality, closed over Christmas, flat YoY | Forecast needs annual seasonality and a closure effect; YoY growth gets a formal test |
# | Heavy concentration (Gini ≈ 0.74): top 10% of customers ≈ 64% of revenue | Lifetime-value modelling and segmentation matter more than average metrics |
# | B2B buying rhythm (weekday office hours) | Recency relative to a customer's own cycle is a key churn feature |

# %%
con.close()
