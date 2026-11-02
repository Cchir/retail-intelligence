"""Retail Intelligence dashboard.

Reads only the serving-layer parquet files in dashboard/data (written by `retail export`),
so it runs anywhere without the warehouse:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data"

# Stratum brand palette (matches stratumdata.org): used as data series, not decoration.
COBALT, AMBER, TEAL, GREY = "#8AA0FF", "#F2B65C", "#58D6C2", "#828D9E"
SURFACE, LINE, TEXT = "#141A24", "#242E3D", "#C5CDDA"
SEQ = ["#141A24", "#26325A", "#3B4C95", "#5A6CF0", "#8AA0FF", "#C9D3FF"]

st.set_page_config(page_title="Retail Intelligence · Stratum", page_icon="▪", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap');
    html, body, [class*="css"], .stMarkdown, p, li { font-family: 'IBM Plex Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -0.02em; }
    .eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: .14em;
               text-transform: uppercase; color: #8AA0FF; }
    div[data-testid="stMetric"] { background: #141A24; border: 1px solid #1B232F;
               border-radius: 12px; padding: 14px 16px; }
    [data-testid="stMetricValue"] { font-size: clamp(1.15rem, 1.7vw, 1.65rem); font-family: 'Space Grotesk', sans-serif; }
    /* Streamlit ellipsises metrics in narrow columns ("£1..."); let them shrink and wrap instead. */
    [data-testid="stMetricValue"] div, [data-testid="stMetricLabel"] div, [data-testid="stMetricLabel"] p,
    [data-testid="stMetricLabel"] div.stMarkdownEllipsis, [data-testid="stMetricLabel"] div.stMarkdownEllipsis p {
        overflow: visible !important; text-overflow: clip !important; white-space: normal !important;
        overflow-wrap: normal !important; word-break: normal !important; }
    [data-testid="stMetricLabel"] p { font-family: 'IBM Plex Sans', sans-serif; font-size: 13px; color: #828D9E; }
    .finding { background: #141A24; border: 1px solid #1B232F; border-left: 3px solid var(--c, #8AA0FF);
               border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; }
    .finding .q { color: #EEF2F8; font-weight: 500; }
    .finding .m { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #828D9E; }
    .block-container { padding-top: 3rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- data
@st.cache_resource
def db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for f in DATA.glob("*.parquet"):
        con.execute(f"create view {f.stem} as select * from read_parquet('{f.as_posix()}')")
    return con


@st.cache_data
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    return db().execute(sql, list(params)).df()


@st.cache_data
def load_json(name: str) -> dict:
    return json.loads((DATA / name).read_text())


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font={"family": "IBM Plex Sans", "color": TEXT, "size": 13},
        margin={"l": 10, "r": 10, "t": 40, "b": 10}, legend={"orientation": "h", "y": -0.18},
        hoverlabel={"bgcolor": SURFACE, "font_family": "IBM Plex Mono"},
        title={"font": {"family": "Space Grotesk", "size": 16}},
    )
    fig.update_xaxes(gridcolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


def gbp(x: float) -> str:
    return f"£{x/1e6:,.2f}m" if abs(x) >= 1e6 else f"£{x/1e3:,.1f}k" if abs(x) >= 1e4 else f"£{x:,.0f}"


metrics = load_json("metrics.json")
quality = load_json("data_quality.json")
bounds = q("select min(date_key) lo, max(date_key) hi from mart_daily_kpis").iloc[0]

# ---------------------------------------------------------------- header + filters
st.markdown('<span class="eyebrow">Stratum · case study</span>', unsafe_allow_html=True)
st.title("Retail Intelligence")
st.caption(
    "UK online giftware wholesaler, Dec 2009 – Dec 2011 · 1.07M raw transactions → "
    "cleaned star schema → statistical models → this dashboard."
)

with st.sidebar:
    st.markdown('<span class="eyebrow">Filters</span>', unsafe_allow_html=True)
    date_range = st.date_input("Period", (bounds.lo.date(), bounds.hi.date()),
                               min_value=bounds.lo.date(), max_value=bounds.hi.date())
    countries = q("select country from mart_country order by revenue desc")["country"].tolist()
    market = st.radio("Market", ["All", "United Kingdom", "International"], horizontal=False)
    picked = st.multiselect("Countries", countries, placeholder="All countries")
    st.divider()
    st.caption("Filters apply to the Overview tab. Model outputs are fixed snapshots as of 9 Dec 2011.")
    st.markdown("[stratumdata.org](https://stratumdata.org)")

d0, d1 = (date_range if isinstance(date_range, tuple) and len(date_range) == 2
          else (bounds.lo.date(), bounds.hi.date()))
where, params = ["date_key between ? and ?", "not has_outlier"], [d0, d1]
if market == "United Kingdom":
    where.append("country = 'United Kingdom'")
elif market == "International":
    where.append("country <> 'United Kingdom'")
if picked:
    where.append(f"country in ({', '.join('?' * len(picked))})")
    params += picked
WHERE = " and ".join(where)

tabs = st.tabs(["Overview", "Customers", "Predictive models", "Statistical findings", "Data pipeline"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    cur = q(f"""select sum(order_value) revenue, count(*) orders,
                count(distinct customer_key) customers, median(order_value) aov,
                avg(is_guest::int) guest_share from fct_orders where {WHERE}""", tuple(params))
    # Same window one year earlier, for deltas.
    prev_params = [pd.Timestamp(d0) - pd.DateOffset(years=1), pd.Timestamp(d1) - pd.DateOffset(years=1), *params[2:]]
    prev = q(f"""select sum(order_value) revenue, count(*) orders,
                 count(distinct customer_key) customers, median(order_value) aov
                 from fct_orders where {WHERE}""", tuple(prev_params))
    c, p = cur.iloc[0], prev.iloc[0]

    # A YoY delta is only meaningful when the whole comparison window is inside the data.
    comparable = prev_params[0] >= pd.Timestamp(bounds.lo)

    def delta(a, b):
        return f"{a / b - 1:+.1%} vs same period last year" if comparable and pd.notna(b) and b else None

    k = st.columns(5)
    k[0].metric("Revenue", gbp(c.revenue or 0), delta(c.revenue, p.revenue))
    k[1].metric("Orders", f"{int(c.orders):,}", delta(c.orders, p.orders))
    k[2].metric("Customers", f"{int(c.customers):,}", delta(c.customers, p.customers))
    k[3].metric("Median order", gbp(c.aov or 0), delta(c.aov, p.aov))
    k[4].metric("Guest checkout share", f"{(c.guest_share or 0):.1%}")

    weekly = q(f"""select date_trunc('week', date_key) week_start, sum(order_value) revenue, count(*) orders
                   from fct_orders where {WHERE} group by 1 order by 1""", tuple(params))
    fig = px.area(weekly, x="week_start", y="revenue", title="Weekly revenue",
                  color_discrete_sequence=[COBALT])
    fig.update_traces(line_width=2, fillcolor="rgba(138,160,255,0.12)",
                      hovertemplate="week of %{x|%d %b %Y}<br>£%{y:,.0f}<extra></extra>")
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None, tickprefix="£")
    st.plotly_chart(style(fig), use_container_width=True)

    left, right = st.columns([1.15, 1])
    with left:
        monthly = q(f"""select year(date_key)::varchar yr, month(date_key) m, sum(order_value) revenue
                        from fct_orders where {WHERE} group by 1, 2 order by 1, 2""", tuple(params))
        fig = px.line(monthly, x="m", y="revenue", color="yr", markers=True,
                      title="Month by month, year over year",
                      color_discrete_map={"2009": GREY, "2010": TEAL, "2011": COBALT})
        fig.update_xaxes(tickvals=list(range(1, 13)), ticktext=list("JFMAMJJASOND"), title=None)
        fig.update_yaxes(title=None)
        st.plotly_chart(style(fig), use_container_width=True)
    with right:
        geo = q(f"""select country, sum(order_value) revenue from fct_orders where {WHERE}
                    and country is not null group by 1 order by 2 desc limit 10""", tuple(params))
        fig = px.bar(geo.iloc[::-1], x="revenue", y="country", orientation="h", log_x=True,
                     title="Top countries (log scale)", color_discrete_sequence=[COBALT])
        fig.update_yaxes(title=None)
        fig.update_xaxes(title=None)
        st.plotly_chart(style(fig), use_container_width=True)

    dow = q(f"""select dayname(date_key) weekday, isodow(date_key) d, sum(order_value) revenue
                from fct_orders where {WHERE} group by 1, 2 order by 2""", tuple(params))
    fig = px.bar(dow, x="weekday", y="revenue", title="Revenue by weekday: a weekday B2B business",
                 color_discrete_sequence=[TEAL])
    fig.update_xaxes(title=None)
    fig.update_yaxes(title=None)
    st.plotly_chart(style(fig, 300), use_container_width=True)

# ---------------------------------------------------------------- customers
with tabs[1]:
    seg = q("select * from segment_summary")
    a, b = st.columns([1, 1.25])
    with a:
        st.subheader("RFM segments")
        fig = px.treemap(seg, path=["segment"], values="revenue", color="revenue_share",
                         color_continuous_scale=SEQ, custom_data=["customers", "revenue_share"])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[1]:.0%} of revenue",
                          hovertemplate="%{label}<br>%{customdata[0]:,} customers<br>£%{value:,.0f}<extra></extra>")
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style(fig, 380), use_container_width=True)
    with b:
        st.subheader("Segment profile")
        st.dataframe(
            seg, hide_index=True, use_container_width=True,
            column_config={
                "revenue": st.column_config.NumberColumn("Revenue", format="£%,.0f"),
                "monetary": st.column_config.NumberColumn("Median spend", format="£%,.0f"),
                "recency_days": st.column_config.NumberColumn("Median recency (days)", format="%d"),
                "frequency": st.column_config.NumberColumn("Median orders", format="%d"),
                "revenue_share": st.column_config.ProgressColumn("Revenue share", format="percent",
                                                                 min_value=0, max_value=1),
            },
        )

    st.subheader("Cohort retention")
    coh = q("select * from mart_cohort_retention where months_since_first between 1 and 12")
    grid = coh.pivot(index="cohort", columns="months_since_first", values="retention")
    fig = px.imshow(grid, color_continuous_scale=SEQ, aspect="auto", text_auto=".0%",
                    labels={"x": "months since first purchase", "y": "acquisition cohort", "color": "active"})
    fig.update_traces(hovertemplate="cohort %{y}<br>month %{x}: %{z:.1%} active<extra></extra>",
                      textfont_size=10)
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style(fig, 560), use_container_width=True)
    st.caption("Dec 2009 looks unusually loyal because the data starts then: it contains customers acquired "
               "in earlier years. Later cohorts show true new-customer behaviour.")

    st.subheader("Predicted 12-month customer lifetime value")
    clv = q("""select c.*, s.segment, s.country from customer_clv c
               left join customer_segments s using (customer_key)""")
    m = metrics["clv"]
    k = st.columns(4)
    k[0].metric("Predicted value, next 12 months", gbp(m["total_12m"]))
    k[1].metric("Share held by top 10%", f"{m['top_decile_share']:.0%}")
    k[2].metric("Expected orders, next 12 months", f"{clv['exp_purchases_12m'].sum():,.0f}",
                help="Sum of BG/NBD conditional expectations over identified customers")
    k[3].metric("Holdout error (26 wks)", f"{m['validation']['predicted_total'] / m['validation']['actual_total'] - 1:+.1%}",
                help="Predicted vs actual purchases on data held out from fitting")
    a, b = st.columns([1.2, 1])
    with a:
        by_seg = (clv.groupby("segment", as_index=False)
                  .agg(clv_12m=("clv_12m", "sum"), customers=("customer_key", "size"))
                  .sort_values("clv_12m"))
        fig = px.bar(by_seg, x="clv_12m", y="segment", orientation="h", custom_data=["customers"],
                     title="Where next year's value sits, by RFM segment",
                     color=by_seg["segment"].isin(["Champions", "Loyal"]).map({True: "core", False: "other"}),
                     color_discrete_map={"core": COBALT, "other": GREY})
        fig.update_traces(hovertemplate="%{y}<br>£%{x:,.0f} predicted · %{customdata[0]:,} customers<extra></extra>")
        fig.update_xaxes(tickprefix="£", title=None)
        fig.update_yaxes(title=None)
        fig.update_layout(showlegend=False)
        st.plotly_chart(style(fig, 420), use_container_width=True)
    with b:
        st.markdown("**Highest-value customers to protect**")
        st.dataframe(
            clv.nlargest(15, "clv_12m")[["customer_key", "country", "p_alive", "clv_12m"]],
            hide_index=True, use_container_width=True, height=420,
            column_config={"customer_key": st.column_config.NumberColumn("Customer", format="%d"),
                           "p_alive": st.column_config.ProgressColumn("P(alive)", min_value=0, max_value=1, format="%.2f"),
                           "clv_12m": st.column_config.NumberColumn("12m value", format="£%,.0f")},
        )

# ---------------------------------------------------------------- predictive
with tabs[2]:
    st.subheader("Who will buy again in the next 90 days?")
    meta = metrics["propensity"]["meta"]
    st.caption(f"Trained on {meta['train_rows']:,} customer-snapshots at 4 quarterly cutoffs; "
               f"tested out-of-time on the {meta['test_cutoff']} cutoff ({meta['test_rows']:,} customers, "
               f"base rate {meta['base_rate_test']:.0%}).")
    scores = q("select * from propensity_scores")
    cols = st.columns(len(scores))
    for col, (_, r) in zip(cols, scores.iterrows(), strict=True):
        col.metric(r["model"].capitalize(), f"AUC {r['roc_auc']:.3f}", f"lift@10% {r['lift_top_decile']:.2f}x",
                   delta_color="off")

    a, b = st.columns(2)
    with a:
        roc = q("select * from propensity_roc")
        fig = px.line(roc, x="fpr", y="tpr", color="model", title="ROC curve (out-of-time test)",
                      color_discrete_sequence=[GREY, AMBER, COBALT],
                      labels={"fpr": "false positive rate", "tpr": "true positive rate"})
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line={"dash": "dot", "color": GREY})
        st.plotly_chart(style(fig, 380), use_container_width=True)
    with b:
        imp = q("select * from propensity_importance order by importance")
        fig = px.bar(imp, x="importance", y="feature", orientation="h", error_x="std",
                     title="What drives the prediction (permutation importance)",
                     color_discrete_sequence=[COBALT])
        fig.update_yaxes(title=None)
        st.plotly_chart(style(fig, 380), use_container_width=True)

    st.markdown("#### Campaign simulator")
    st.caption("If the account team can only contact part of the customer base, how many of next quarter's "
               "buyers do they reach by following the model instead of contacting customers at random?")
    scored = q("select * from propensity_test_scored order by p_purchase_90d desc")
    share = st.slider("Share of customers contacted", 5, 100, 20, 5, format="%d%%")
    n = int(len(scored) * share / 100)
    captured = scored["actual"].iloc[:n].sum()
    total = scored["actual"].sum()
    s = st.columns(3)
    s[0].metric("Customers contacted", f"{n:,}")
    s[1].metric("Buyers reached (model)", f"{captured:,}", f"{captured / total:.0%} of all buyers", delta_color="off")
    s[2].metric("Buyers reached (random)", f"{int(total * share / 100):,}", f"model finds {captured / max(total * share / 100, 1):.2f}x more",
                delta_color="off")
    gains = pd.DataFrame({"contacted": (pd.RangeIndex(1, len(scored) + 1) / len(scored)),
                          "model": scored["actual"].cumsum().values / total})
    fig = go.Figure()
    fig.add_scatter(x=gains["contacted"], y=gains["model"], name="model", line={"color": COBALT, "width": 2.5})
    fig.add_scatter(x=[0, 1], y=[0, 1], name="random", line={"color": GREY, "dash": "dot"})
    fig.add_vline(x=share / 100, line_color=AMBER)
    fig.update_xaxes(tickformat=".0%", title="customers contacted")
    fig.update_yaxes(tickformat=".0%", title="buyers reached")
    fig.update_traces(mode="lines")
    fig.update_layout(title="Cumulative gains")
    st.plotly_chart(style(fig, 340), use_container_width=True)

    st.divider()
    st.subheader("Revenue forecast")
    fs = q("select * from forecast_scores order by mase")
    best = metrics["forecast"]["best_model"]
    hist = q("select * from weekly_revenue")
    bt = q("select * from forecast_backtest")
    fut = q("select * from forecast_future")
    show = st.multiselect("Backtest models", fs["model"].tolist(), default=[best, "seasonal naive"])
    fig = go.Figure()
    fig.add_scatter(x=hist["week_start"], y=hist["revenue"], name="actual", line={"color": TEXT, "width": 1.6})
    palette = dict(zip(fs["model"], [COBALT, GREY, TEAL, AMBER, "#E0736B", "#C9D3FF"], strict=False))
    for mname in show:
        d = bt[bt["model"] == mname]
        fig.add_scatter(x=d["week_start"], y=d["forecast"], name=f"backtest · {mname}",
                        line={"color": palette[mname], "width": 2})
    fig.add_scatter(x=fut["week_start"], y=fut["upper"], line={"width": 0}, showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=fut["week_start"], y=fut["lower"], fill="tonexty", fillcolor="rgba(138,160,255,0.15)",
                    line={"width": 0}, name="80% interval")
    fig.add_scatter(x=fut["week_start"], y=fut["forecast"], name="forecast · next 12 weeks",
                    line={"color": COBALT, "width": 2.5, "dash": "dash"})
    fig.update_yaxes(tickprefix="£", title=None)
    fig.update_traces(mode="lines")
    st.plotly_chart(style(fig, 420), use_container_width=True)
    st.dataframe(fs, hide_index=True, use_container_width=True,
                 column_config={"mase": st.column_config.NumberColumn("MASE", format="%.3f", help="<1 beats seasonal naive"),
                                "mape": st.column_config.NumberColumn("MAPE", format="percent"),
                                "total_error_pct": st.column_config.NumberColumn("Quarter total error", format="percent"),
                                "coverage_80": st.column_config.NumberColumn("80% interval coverage", format="percent")})

# ---------------------------------------------------------------- findings
with tabs[3]:
    st.subheader("What the data says, tested formally")
    st.caption("Effect sizes with 95% confidence intervals; p-values Holm-corrected for 5 simultaneous tests.")
    tests = q("select * from hypothesis_tests")
    for _, t in tests.iterrows():
        color = TEAL if t["significant"] else AMBER
        verdict = "Significant" if t["significant"] else "Not significant"
        fmt = (lambda v: f"{v:,.0f}") if abs(t["ci_high"]) >= 10 else (lambda v: f"{v:.3f}")
        ci = f" · 95% CI [{fmt(t['ci_low'])}, {fmt(t['ci_high'])}]" if pd.notna(t["ci_low"]) else ""
        st.markdown(
            f"""<div class="finding" style="--c:{color}">
            <div class="q">{t['question']}</div>
            <div style="margin:6px 0 4px">{t['effect']}</div>
            <div class="m">{verdict} (p_holm = {t['p_holm']:.2g}){ci} · {t['method']} · {t['groups']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    st.subheader("Products bought together")
    mb = q("select * from market_basket")
    st.dataframe(mb, hide_index=True, use_container_width=True,
                 column_config={"support": st.column_config.NumberColumn("Support", format="percent"),
                                "confidence_a_to_b": st.column_config.NumberColumn("Confidence A→B", format="percent"),
                                "lift": st.column_config.ProgressColumn("Lift", min_value=0, max_value=float(mb["lift"].max()), format="%.1f")})

# ---------------------------------------------------------------- pipeline
with tabs[4]:
    st.subheader("How the data gets here")
    st.graphviz_chart(
        """
        digraph {
          rankdir=LR; bgcolor="transparent";
          node [shape=box style="rounded,filled" fillcolor="#141A24" color="#242E3D" fontcolor="#EEF2F8" fontname="Helvetica" fontsize=11];
          edge [color="#828D9E"];
          src [label="UCI archive\\n(.xlsx, 2 sheets)"];
          bronze [label="Bronze\\nparquet, untouched\\n+ lineage cols"];
          silver [label="Silver\\ntyped, standardised\\nrow_status tags"];
          marts [label="DuckDB star schema\\ndims · facts · marts\\n(SQL models)"];
          dq [label="15 data quality\\nchecks" fillcolor="#2A2418" color="#F2B65C"];
          models [label="Analysis\\nstats tests · RFM · CLV\\npropensity · forecast"];
          serve [label="Serving layer\\nparquet, 1 MB"];
          app [label="This dashboard" fillcolor="#1D2546" color="#8AA0FF"];
          src -> bronze [label=" extract"]; bronze -> silver [label=" transform"];
          silver -> marts [label=" load"]; marts -> dq; marts -> models; models -> serve; marts -> serve; serve -> app;
        }
        """
    )
    a, b = st.columns([1, 1.2])
    with a:
        rs = q("select * from row_status")
        fig = px.bar(rs.iloc[::-1], x="n_rows", y="row_status", orientation="h", log_x=True,
                     title="Every raw row accounted for", text="n_rows",
                     color=rs.iloc[::-1]["row_status"].eq("valid_sale").map({True: "kept", False: "excluded"}),
                     color_discrete_map={"kept": COBALT, "excluded": AMBER})
        fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[1.5, 6.8], title=None)
        fig.update_yaxes(title=None)
        fig.update_layout(showlegend=False)
        st.plotly_chart(style(fig, 360), use_container_width=True)
    with b:
        checks = pd.DataFrame(quality["checks"])
        checks["result"] = checks.apply(
            lambda r: "✅ pass" if r["passed"] else ("⚠️ warn" if r["severity"] == "warn" else "❌ fail"), axis=1)
        st.markdown(f"**Data quality checks** ({checks['passed'].sum()}/{len(checks)} passing)")
        st.dataframe(checks[["name", "severity", "failures", "result"]], hide_index=True,
                     use_container_width=True, height=360)
