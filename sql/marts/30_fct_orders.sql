-- Grain: one order (invoice). The unit most business questions are actually about.
create or replace table fct_orders as
select
    invoice_no, any_value(customer_key) as customer_key, min(invoice_ts) as order_ts,
    min(date_key) as date_key, any_value(country) as country,
    count(*) as n_lines, sum(quantity) as units, round(sum(line_revenue), 2) as order_value,
    bool_or(is_outlier) as has_outlier, any_value(is_guest) as is_guest
from fct_sales
group by invoice_no;
