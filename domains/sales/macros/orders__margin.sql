{# Shared macros carry their product's prefix (GOV-204). #}
{% macro orders__margin(amount, cost) %}
    ({{ amount }} - {{ cost }})
{% endmacro %}
