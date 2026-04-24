{# SCD Type 2 full refresh for Phase 1; migrate to snapshot + surrogate key in Phase 4. #}
{{ config(
    materialized = 'table',
    schema = 'mart',
    unique_key = 'employee_id',
    post_hook = "CREATE INDEX IF NOT EXISTS idx_dim_emp_dept ON {{ this }}(department)"
) }}

with employees as (
    select * from {{ ref('stg_employees') }}
),

-- Peer-group median income: used to flag below-median employees
peer_medians as (
    select
        department,
        job_level,
        percentile_cont(0.50) within group (order by monthly_income) as peer_median_income,
        percentile_cont(0.25) within group (order by monthly_income) as peer_p25_income,
        percentile_cont(0.75) within group (order by monthly_income) as peer_p75_income
    from employees
    where is_active
    group by department, job_level
),

enriched as (
    select
        e.*,
        pm.peer_median_income,
        pm.peer_p25_income,
        pm.peer_p75_income,
        case
            when e.monthly_income < pm.peer_median_income then true
            else false
        end                                                     as is_below_peer_median,
        round(
            (e.monthly_income / nullif(pm.peer_median_income, 0) - 1)::numeric,
            4
        )                                                       as income_vs_peer_median_pct,

        -- Risk factor flags (used by ML layer)
        e.job_satisfaction < 2                                  as flag_low_satisfaction,
        e.years_since_last_promotion > 3                        as flag_stagnant_career,
        e.monthly_income < pm.peer_median_income                as flag_below_peer_pay,
        e.performance_rating >= 4                               as flag_high_performer,

        -- Attrition indicator
        e.termination_date is not null                          as has_attrited,

        current_timestamp                                       as dbt_updated_at,
        true                                                    as dbt_is_current_record

    from employees e
    left join peer_medians pm
        on e.department = pm.department
       and e.job_level   = pm.job_level
)

select * from enriched
