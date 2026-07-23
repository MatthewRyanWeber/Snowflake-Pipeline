select
    v:encounter_id::string           as encounter_id,
    v:patient_id::string             as patient_id,
    v:start::timestamp_ntz           as started_at,
    v:stop::timestamp_ntz            as stopped_at,
    v:encounter_class::string        as encounter_class,
    v:provider.name::string          as provider_name,
    v:provider.facility_id::string   as facility_id,
    v:provider.facility_name::string as facility_name,
    v:provider.city::string          as city,
    v:provider.state::string         as state,
    datediff('minute', v:start::timestamp_ntz, v:stop::timestamp_ntz) as duration_minutes,
    array_size(v:observations)       as observation_count,
    array_size(v:conditions)         as condition_count
from {{ source('raw', 'encounters_json') }}
