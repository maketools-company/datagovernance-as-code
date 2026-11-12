-- Public interface `orders`, version 1. Its columns are promised by orders_v1.odcs.yaml.
select
    order_id,
    customer_id,
    ordered_on,
    amount,
    status,
    cast(current_timestamp as timestamp) as loaded_at
from {{ ref('gld_orders') }}
