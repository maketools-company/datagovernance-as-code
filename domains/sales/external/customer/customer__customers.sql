-- Consumer zone: the only place where Customer's data enters the Sales domain.
-- A cross-project reference to Customer's public interface, version 1, checked by dbt.
select * from {{ ref('customer', 'customers', v=1) }}
