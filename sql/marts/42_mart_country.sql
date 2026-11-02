create or replace table mart_country as
select country, count(distinct customer_key) customers, count(*) orders,
       round(sum(order_value), 2) revenue, round(median(order_value), 2) median_order_value
from fct_orders where not has_outlier and country is not null
group by country order by revenue desc;
