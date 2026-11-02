"""Hypothesis tests on business questions. Each returns a tidy dict: question, method,
statistic, p-value, effect size with a confidence interval, and a plain-English conclusion.

Effect sizes and intervals are reported alongside p-values on purpose: with ~5,000 customers
almost anything is "significant", so the useful question is always "by how much?".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

from retail.analysis.common import DATA_END, query

RNG = np.random.default_rng(42)


def _bootstrap_diff(a, b, stat=np.median, n=5000):
    a, b = np.asarray(a), np.asarray(b)
    boots = np.array([stat(RNG.choice(a, len(a))) - stat(RNG.choice(b, len(b))) for _ in range(n)])
    return np.percentile(boots, [2.5, 97.5])


def peak_season_retention(orders: pd.DataFrame) -> dict:
    """Gift-season customers are often assumed to be one-off buyers. Is that true here?"""
    first = orders.groupby("customer_key")["date_key"].min().rename("first")
    df = orders.merge(first, left_on="customer_key", right_index=True)
    cohort = first[first <= DATA_END - pd.Timedelta(days=180)].to_frame()
    repeat = df[(df["date_key"] > df["first"]) & (df["date_key"] <= df["first"] + pd.Timedelta(days=180))]
    cohort["returned"] = cohort.index.isin(repeat["customer_key"])
    cohort["peak"] = cohort["first"].dt.month.isin([11, 12])
    g = cohort.groupby("peak")["returned"].agg(["sum", "count"])
    g = g.reindex([True, False])
    count, nobs = g["sum"].to_numpy(), g["count"].to_numpy()
    z, p = proportions_ztest(count, nobs)
    lo, hi = confint_proportions_2indep(count[0], nobs[0], count[1], nobs[1])
    rates = count / nobs
    return {
        "question": "Do customers acquired in Nov-Dec (gift season) return at a different rate within 180 days?",
        "method": "Two-proportion z-test; Newcombe CI on the difference",
        "groups": f"peak n={nobs[0]}, rest n={nobs[1]}",
        "statistic": z, "p_value": p,
        "effect": f"{rates[0]:.1%} vs {rates[1]:.1%} return rate",
        "effect_value": rates[0] - rates[1], "ci_low": lo, "ci_high": hi,
    }


def uk_vs_international_aov(orders: pd.DataFrame) -> dict:
    uk = orders.loc[orders["country"] == "United Kingdom", "order_value"]
    intl = orders.loc[(orders["country"] != "United Kingdom") & orders["country"].notna(), "order_value"]
    u, p = stats.mannwhitneyu(intl, uk, alternative="two-sided")
    lo, hi = _bootstrap_diff(intl.values, uk.values)
    # Common-language effect size: P(random intl order > random UK order).
    cles = u / (len(intl) * len(uk))
    return {
        "question": "Do international customers place larger orders than UK customers?",
        "method": "Mann-Whitney U (order values are heavily skewed); bootstrap CI of median difference",
        "groups": f"international n={len(intl)}, UK n={len(uk)}",
        "statistic": u, "p_value": p,
        "effect": f"median £{intl.median():,.0f} vs £{uk.median():,.0f}; P(intl > UK) = {cles:.2f}",
        "effect_value": intl.median() - uk.median(), "ci_low": lo, "ci_high": hi,
    }


def weekday_effect() -> dict:
    d = query("select day_name, gross_revenue from mart_daily_kpis where orders > 0")
    groups = [g["gross_revenue"].values for _, g in d.groupby("day_name")]
    h, p = stats.kruskal(*groups)
    n, k = len(d), len(groups)
    eps2 = (h - k + 1) / (n - k)  # epsilon-squared effect size for Kruskal-Wallis
    med = d.groupby("day_name")["gross_revenue"].median().sort_values(ascending=False)
    return {
        "question": "Does daily revenue differ by day of week?",
        "method": "Kruskal-Wallis H test; epsilon-squared effect size",
        "groups": ", ".join(f"{k[:3]} £{v/1000:,.0f}k" for k, v in med.items()),
        "statistic": h, "p_value": p,
        "effect": f"epsilon² = {eps2:.3f}; Saturday trading is almost nil",
        "effect_value": eps2, "ci_low": np.nan, "ci_high": np.nan,
    }


def yoy_growth() -> dict:
    """Is Jan-Nov 2011 revenue per trading day really higher than Jan-Nov 2010?"""
    d = query("select date_key, year, month, gross_revenue from mart_daily_kpis "
              "where orders > 0 and month between 1 and 11 and year in (2010, 2011)")
    a = d.loc[d["year"] == 2011, "gross_revenue"].values
    b = d.loc[d["year"] == 2010, "gross_revenue"].values
    t, p = stats.ttest_ind(a, b, equal_var=False)
    lo, hi = _bootstrap_diff(a, b, stat=np.mean)
    return {
        "question": "Did average daily revenue grow year over year (Jan-Nov 2011 vs 2010)?",
        "method": "Welch's t-test; bootstrap CI of the mean difference",
        "groups": f"2011 n={len(a)} days, 2010 n={len(b)} days",
        "statistic": t, "p_value": p,
        "effect": f"£{a.mean():,.0f} vs £{b.mean():,.0f} per trading day ({a.mean() / b.mean() - 1:+.1%})",
        "effect_value": a.mean() - b.mean(), "ci_low": lo, "ci_high": hi,
    }


def basket_size_vs_returns() -> dict:
    """Are customers who return items more valuable or less valuable?"""
    d = query("""
        with r as (select customer_key, count(distinct invoice_no) n_ret from fct_returns
                   where customer_key is not null group by 1)
        select c.customer_key, c.gross_revenue, coalesce(r.n_ret, 0) > 0 as returner
        from dim_customer c left join r on r.customer_key = c.customer_key
    """)
    a = d.loc[d["returner"], "gross_revenue"].values
    b = d.loc[~d["returner"], "gross_revenue"].values
    u, p = stats.mannwhitneyu(a, b)
    lo, hi = _bootstrap_diff(a, b)
    return {
        "question": "Do customers who return items spend more overall than those who never do?",
        "method": "Mann-Whitney U; bootstrap CI of median difference",
        "groups": f"returners n={len(a)}, non-returners n={len(b)}",
        "statistic": u, "p_value": p,
        "effect": f"median lifetime spend £{np.median(a):,.0f} vs £{np.median(b):,.0f}",
        "effect_value": np.median(a) - np.median(b), "ci_low": lo, "ci_high": hi,
    }


def run(orders: pd.DataFrame) -> pd.DataFrame:
    rows = [peak_season_retention(orders), uk_vs_international_aov(orders), weekday_effect(),
            yoy_growth(), basket_size_vs_returns()]
    df = pd.DataFrame(rows)
    # Five tests on the same data: control the family-wise error rate.
    df["p_holm"] = multipletests(df["p_value"], method="holm")[1]
    df["significant"] = df["p_holm"] < 0.05
    return df


def market_basket(min_support: float = 0.01, top: int = 40) -> pd.DataFrame:
    """Pairwise association rules (support, confidence, lift) computed in SQL."""
    return query(
        """
        with baskets as (select distinct invoice_no, product_key from fct_sales),
        n as (select count(distinct invoice_no)::double total from baskets),
        item as (select product_key, count(*) / (select total from n) support
                 from baskets group by 1 having support >= $s),
        pairs as (
            select a.product_key a, b.product_key b, count(*) / (select total from n) support
            from baskets a join baskets b on a.invoice_no = b.invoice_no and a.product_key < b.product_key
            where a.product_key in (select product_key from item)
              and b.product_key in (select product_key from item)
            group by 1, 2 having support >= $s / 2)
        select pa.product_name item_a, pb.product_name item_b, round(p.support, 4) support,
               round(p.support / ia.support, 3) confidence_a_to_b,
               round(p.support / (ia.support * ib.support), 2) lift
        from pairs p
        join item ia on ia.product_key = p.a join item ib on ib.product_key = p.b
        join dim_product pa on pa.product_key = p.a join dim_product pb on pb.product_key = p.b
        order by lift desc limit $top
        """,
        s=min_support, top=top,
    )
