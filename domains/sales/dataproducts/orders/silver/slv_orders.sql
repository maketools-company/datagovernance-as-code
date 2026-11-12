-- Valid orders only: cancelled orders are not sales. Private.
select *
from {{ ref('stg_orders') }}
where status <> 'cancelled'
