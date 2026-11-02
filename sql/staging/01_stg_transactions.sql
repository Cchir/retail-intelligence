-- Silver layer: one row per source line, typed, standardised and status-tagged in Python.
-- Kept in full so every exclusion is auditable.
create or replace view stg_transactions as
select * from silver_transactions;
