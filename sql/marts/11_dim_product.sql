create or replace table dim_product as
select
    stock_code                                         as product_key,
    any_value(product_name)                            as product_name,
    median(unit_price)                                 as median_unit_price,
    min(invoice_date)::date                            as first_sold,
    max(invoice_date)::date                            as last_sold,
    count(distinct invoice_no)                         as n_orders,
    sum(quantity)                                      as units_sold,
    round(sum(line_revenue), 2)                        as gross_revenue
from stg_transactions
where row_status = 'valid_sale'
group by stock_code;
