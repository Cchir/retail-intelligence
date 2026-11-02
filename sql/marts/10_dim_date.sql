create or replace table dim_date as
with bounds as (
    select min(invoice_date)::date as d0, max(invoice_date)::date as d1 from stg_transactions
)
select
    d::date                                   as date_key,
    year(d)                                   as year,
    quarter(d)                                as quarter,
    month(d)                                  as month,
    strftime(d, '%Y-%m')                      as year_month,
    date_trunc('week', d)::date               as week_start,
    dayofweek(d)                              as day_of_week,   -- 0 = Sunday
    strftime(d, '%A')                         as day_name,
    dayofweek(d) in (0, 6)                    as is_weekend,
    month(d) in (11, 12)                      as is_peak_season
from bounds, range(d0, d1 + interval 1 day, interval 1 day) t(d);
