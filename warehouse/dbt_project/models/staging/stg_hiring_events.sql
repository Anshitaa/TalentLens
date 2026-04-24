{{
  config(
    materialized = 'view',
    schema = 'staging'
  )
}}

with source as (
    select * from {{ source('raw', 'hiring_funnel_events') }}
),

normalized as (
    select
        event_id::text          as event_id,
        candidate_id::text      as candidate_id,
        upper(trim(stage))      as stage,
        case upper(trim(stage))
            when 'APPLICATION'  then 1
            when 'PHONE_SCREEN' then 2
            when 'INTERVIEW'    then 3
            when 'OFFER'        then 4
            when 'HIRE'         then 5
            when 'REJECT'       then 5
            else 0
        end                     as stage_order,
        event_date,
        department,

        -- Extract typed fields from JSONB payload
        (payload->>'passed')::boolean                   as passed,
        (payload->>'offered_salary')::numeric           as offered_salary,
        (payload->>'accepted')::boolean                 as offer_accepted,
        (payload->>'round')::smallint                   as interview_round,
        _ingested_at

    from source
    where candidate_id is not null
      and stage is not null
)

select * from normalized
