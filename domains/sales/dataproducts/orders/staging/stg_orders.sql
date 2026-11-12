-- Raw orders, renamed and typed. Private.
select
    cast(order_id as integer)          as order_id,
    cast(customer_id as integer)       as customer_id,
    cast(ordered_on as date)           as ordered_on,
    cast(amount_eur as decimal(12, 2)) as amount,
    cast(cost_eur as decimal(12, 2))   as cost,
    status
from {{ ref('orders__raw_orders') }}
