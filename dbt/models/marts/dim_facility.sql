select
    md5(facility_id)          as facility_sk,
    facility_id,
    facility_name,
    md5(city || '|' || state) as location_sk
from (select distinct facility_id, facility_name, city, state from {{ ref('stg_encounters') }})
