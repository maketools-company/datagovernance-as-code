-- Public interface `customers`, version 1. Its columns are promised by customers_v1.odcs.yaml.
select
    customer_id,
    email,
    first_name,
    country,
    signed_up_on,
    cast(current_timestamp as timestamp) as loaded_at
from {{ ref('gld_customers') }}
