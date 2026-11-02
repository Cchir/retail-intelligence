create or replace table mart_daily_kpis as
with s as (
    select date_key, round(sum(order_value), 2) gross_revenue, count(*) orders,
           count(distinct customer_key) customers, round(avg(order_value), 2) aov
    from fct_orders where not has_outlier group by date_key
), r as (
    select date_key, round(sum(line_revenue), 2) returns_value
    from fct_returns group by date_key
)
select d.*, coalesce(s.gross_revenue, 0) gross_revenue,
       coalesce(r.returns_value, 0) returns_value,
       coalesce(s.gross_revenue, 0) + coalesce(r.returns_value, 0) net_revenue,
       coalesce(s.orders, 0) orders, coalesce(s.customers, 0) customers, s.aov
from dim_date d
left join s using (date_key)
left join r using (date_key);
