select
    e.v:encounter_id::string        as encounter_id,
    obs.value:code::string          as obs_code,
    obs.value:description::string   as obs_description,
    obs.value:value::float          as obs_value,
    obs.value:units::string         as obs_units
from {{ source('raw', 'encounters_json') }} e,
     lateral flatten(input => e.v:observations) obs
