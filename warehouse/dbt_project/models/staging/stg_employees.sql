{{
  config(
    materialized = 'view',
    schema = 'staging'
  )
}}

with source as (
    select * from {{ source('raw', 'hris_employee_snapshot') }}
),

cleaned as (
    select
        employee_id::text                                               as employee_id,
        trim(first_name)                                                as first_name,
        trim(last_name)                                                 as last_name,
        trim(first_name) || ' ' || trim(last_name)                     as full_name,
        lower(trim(email))                                              as email,
        department,
        job_level,
        case
            when job_level like 'IC%' then 'individual_contributor'
            when job_level like 'M%'  then 'manager'
            else 'unknown'
        end                                                             as job_level_type,
        job_role,
        hire_date,
        termination_date,
        coalesce(is_active, termination_date is null)                   as is_active,

        -- Income
        monthly_income,
        monthly_income * 12                                             as annual_income,

        -- Satisfaction scores (coerce nulls to 2 = neutral)
        coalesce(job_satisfaction, 2)                                   as job_satisfaction,
        coalesce(environment_satisfaction, 2)                           as environment_satisfaction,
        coalesce(work_life_balance, 2)                                  as work_life_balance,
        coalesce(performance_rating, 2)                                 as performance_rating,
        round(
            (coalesce(job_satisfaction, 2)
             + coalesce(environment_satisfaction, 2)
             + coalesce(work_life_balance, 2)) / 3.0,
            2
        )                                                               as avg_satisfaction,

        -- Tenure / career features
        coalesce(years_since_last_promotion, 0)                        as years_since_last_promotion,
        coalesce(years_with_current_manager, 0)                        as years_with_current_manager,
        round(
            (current_date - hire_date) / 365.0,
            2
        )                                                               as years_at_company,

        -- Behavioral attributes
        coalesce(distance_from_home, 10)                               as distance_from_home,
        coalesce(num_companies_worked, 1)                               as num_companies_worked,
        coalesce(training_times_last_year, 0)                          as training_times_last_year,
        coalesce(overtime_flag, false)                                  as overtime_flag,

        -- Demographics
        coalesce(education, 3)                                          as education,
        coalesce(education_field, 'Other')                              as education_field,
        coalesce(marital_status, 'Single')                              as marital_status,
        gender,
        age,
        case
            when age < 30 then '18-29'
            when age < 40 then '30-39'
            when age < 50 then '40-49'
            else '50-65'
        end                                                             as age_band,

        manager_id::text                                                as manager_id,
        _ingested_at

    from source
    where employee_id is not null
      and hire_date is not null
      and monthly_income > 0
)

select * from cleaned
