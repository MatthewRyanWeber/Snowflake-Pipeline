with deduped as (
    select *,
           row_number() over (partition by patient_id order by _load_ts desc nulls last) as rn
    from {{ source('raw', 'patients_csv') }}
)
select
    patient_id,
    first_name,
    last_name,
    birth_date::date as birth_date,
    gender,
    city,
    state,
    ssn   as ssn_masked,
    phone as phone_masked
from deduped
where rn = 1
