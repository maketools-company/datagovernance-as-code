-- Raw customers, renamed and typed. Private.
select
    cast(customer_id as integer)   as customer_id,
    lower(trim(email))             as email,
    first_name,
    upper(country_code)            as country_code,
    cast(signed_up_on as date)     as signed_up_on
from {{ ref('customer_profile__raw_customers') }}
