-- One row per real customer: duplicate sign-ups with the same email are merged. Private.
select *
from {{ ref('stg_customers') }}
qualify row_number() over (partition by email order by customer_id) = 1
