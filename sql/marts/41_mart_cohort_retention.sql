-- Monthly acquisition cohorts x months since first purchase.
create or replace table mart_cohort_retention as
with activity as (
    select distinct o.customer_key, date_trunc('month', o.date_key) as active_month
    from fct_orders o where o.customer_key is not null
), cohorts as (
    select customer_key, date_trunc('month', first_order_date) as cohort_month from dim_customer
)
select
    strftime(c.cohort_month, '%Y-%m') as cohort,
    date_diff('month', c.cohort_month, a.active_month) as months_since_first,
    count(distinct a.customer_key) as active_customers,
    max(count(distinct a.customer_key)) over (partition by c.cohort_month) as cohort_size,
    round(count(distinct a.customer_key)
          / max(count(distinct a.customer_key)) over (partition by c.cohort_month), 4) as retention
from activity a join cohorts c using (customer_key)
group by c.cohort_month, a.active_month
order by cohort, months_since_first;
