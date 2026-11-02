-- Grain: one valid invoice line. Guest checkouts (no customer id) stay in revenue facts.
create or replace table fct_sales as
select
    invoice_no, stock_code as product_key, customer_id as customer_key,
    invoice_ts, invoice_date::date as date_key, country,
    quantity, unit_price, line_revenue, is_outlier,
    customer_id is null as is_guest
from stg_transactions
where row_status = 'valid_sale';
