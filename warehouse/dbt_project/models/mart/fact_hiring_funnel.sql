{{
  config(
    materialized = 'table',
    schema = 'mart'
  )
}}

with hiring_events as (
    select * from {{ ref('stg_hiring_events') }}
),

-- Pivot: one row per candidate showing their journey through the funnel
candidate_funnel as (
    select
        candidate_id,
        max(department)                                                         as department,

        min(case when stage = 'APPLICATION'  then event_date end)              as application_date,
        min(case when stage = 'PHONE_SCREEN' then event_date end)              as screen_date,
        min(case when stage = 'INTERVIEW'    then event_date end)              as interview_date,
        min(case when stage = 'OFFER'        then event_date end)              as offer_date,

        max(case when stage = 'OFFER' then offered_salary end)                 as offered_salary,
        bool_or(case when stage = 'OFFER' then coalesce(offer_accepted, false) end) as offer_accepted,

        max(stage_order)                                                        as max_stage_reached,
        count(distinct stage)                                                   as stages_completed

    from hiring_events
    group by candidate_id
),

with_outcome as (
    select
        candidate_id,
        department,
        application_date,
        screen_date,
        interview_date,
        offer_date,
        offered_salary,

        -- Outcome classification
        case
            when offer_accepted = true                       then 'hired'
            when max_stage_reached >= 4 and not offer_accepted then 'rejected'
            when max_stage_reached >= 2                      then 'rejected'
            else 'withdrawn'
        end                                                     as outcome,

        -- Time-to-stage (business days approximated as calendar days)
        case when screen_date    is not null then screen_date    - application_date end as days_to_screen,
        case when interview_date is not null then interview_date - screen_date     end as days_to_interview,
        case when offer_date     is not null then offer_date     - interview_date  end as days_to_offer,
        case
            when offer_date      is not null then offer_date - application_date
            when screen_date     is not null then screen_date - application_date
        end                                                     as days_to_close

    from candidate_funnel
)

select
    {{ dbt_utils.generate_surrogate_key(['candidate_id']) }}    as funnel_id,
    candidate_id,
    department,
    application_date,
    screen_date,
    interview_date,
    offer_date,
    outcome,
    offered_salary,
    days_to_screen,
    days_to_interview,
    days_to_offer,
    days_to_close,
    current_timestamp                                           as _loaded_at
from with_outcome
