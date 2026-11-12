-- Customers with their country name. Private.
select
    c.customer_id,
    c.email,
    c.first_name,
    {{ customer_profile__country_name('c.country_code') }} as country,
    c.signed_up_on
from {{ ref('slv_customers') }} as c
