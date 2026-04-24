{# Populated directly by ml/risk_engine/inference.py (Phase 3).
   This dbt model exposes a clean analytical view joining scores with employee dims.
   Run ml/train_and_score.py before running dbt to populate the source table. #}
{{ config(
    materialized = 'view',
    schema = 'mart'
) }}

with scores as (
    select * from mart.fact_risk_scores
),

employees as (
    select employee_id, full_name, department, job_level, age_band, gender
    from {{ ref('dim_employee') }}
    where dbt_is_current_record
)

select
    s.score_id,
    s.employee_id,
    e.full_name,
    e.department,
    e.job_level,
    e.age_band,
    e.gender,
    s.scored_at,
    s.flight_risk_prob,
    s.anomaly_score,
    s.compliance_flag,
    s.risk_index,
    s.risk_band,
    s.shap_top_feature_1,
    s.shap_top_feature_2,
    s.shap_top_feature_3,
    s.shap_value_1,
    s.shap_value_2,
    s.shap_value_3,
    s.model_version,
    s._loaded_at
from scores s
left join employees e on s.employee_id::text = e.employee_id::text
