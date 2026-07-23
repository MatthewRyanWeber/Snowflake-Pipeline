select
    e.encounter_id,
    to_number(to_char(e.started_at::date, 'YYYYMMDD')) as date_key,
    p.patient_sk,
    md5(e.provider_name) as provider_sk,
    md5(e.facility_id)   as facility_sk,
    e.encounter_class,
    e.duration_minutes,
    e.observation_count,
    e.condition_count
from {{ ref('stg_encounters') }} e
left join {{ ref('dim_patient') }} p
    on p.patient_id = e.patient_id and p.is_current
