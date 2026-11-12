{# Fails when the newest row is older than the latency promised in the contract (GOV-309). #}
{% test customer_profile__recency(model, column_name, max_hours) %}
select max({{ column_name }}) as newest
from {{ model }}
having max({{ column_name }}) < current_timestamp - interval '{{ max_hours }} hours'
{% endtest %}
