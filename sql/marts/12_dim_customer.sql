-- Country is the customer's most frequent country (a handful of IDs appear under two).
create or replace table dim_customer as
with country_rank as (
    select customer_id, country, count(*) n,
           row_number() over (partition by customer_id order by count(*) desc, country) rn
    from stg_transactions
    where row_status = 'valid_sale' and customer_id is not null
    group by customer_id, country
)
select
    s.customer_id                                      as customer_key,
    c.country,
    min(s.invoice_date)::date                          as first_order_date,
    max(s.invoice_date)::date                          as last_order_date,
    strftime(min(s.invoice_date), '%Y-%m')             as acquisition_cohort,
    count(distinct s.invoice_no)                       as n_orders,
    round(sum(s.line_revenue), 2)                      as gross_revenue
from stg_transactions s
join country_rank c on c.customer_id = s.customer_id and c.rn = 1
where s.row_status = 'valid_sale'
group by s.customer_id, c.country;
