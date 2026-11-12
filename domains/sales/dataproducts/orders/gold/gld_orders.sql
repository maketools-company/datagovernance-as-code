-- Orders with their margin. Private: the margin is for the Sales domain only.
select
    order_id,
    customer_id,
    ordered_on,
    amount,
    {{ orders__margin('amount', 'cost') }} as margin,
    status
from {{ ref('slv_orders') }}
