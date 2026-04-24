{% macro risk_band(column_name) %}
    case
        when {{ column_name }} <= 25 then 'Low'
        when {{ column_name }} <= 50 then 'Medium'
        when {{ column_name }} <= 75 then 'High'
        else 'Critical'
    end
{% endmacro %}
