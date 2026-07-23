select
    md5(city || '|' || state) as location_sk,
    city,
    state,
    case when state in ('NY','NJ','CT','MA','PA') then 'Northeast'
         when state in ('CA','WA','OR') then 'West'
         when state in ('TX') then 'South'
         when state in ('IL') then 'Midwest'
         else 'Other' end as region
from (select distinct city, state from {{ ref('stg_encounters') }})
