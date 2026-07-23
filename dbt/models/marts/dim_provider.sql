select
    md5(provider_name) as provider_sk,
    provider_name
from (select distinct provider_name from {{ ref('stg_encounters') }})
