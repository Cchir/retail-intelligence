-- Grain: one cancelled line (credit note). Revenue is negative.
create or replace table fct_returns as
select
    invoice_no, stock_code as product_key, customer_id as customer_key,
    invoice_ts, invoice_date::date as date_key, country,
    -quantity as units_returned, unit_price, line_revenue
from stg_transactions
where row_status = 'cancellation';
