{# Shared macros carry their product's prefix (GOV-204): dbt sees every macro of the project. #}
{% macro customer_profile__country_name(code) %}
    case {{ code }}
        when 'FR' then 'France'
        when 'GB' then 'United Kingdom'
        when 'ES' then 'Spain'
        when 'DE' then 'Germany'
        else 'Other'
    end
{% endmacro %}
