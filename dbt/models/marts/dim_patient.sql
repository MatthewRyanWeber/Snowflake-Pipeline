select
    dbt_scd_id      as patient_sk,
    patient_id,
    first_name,
    last_name,
    birth_date,
    gender,
    city,
    state,
    dbt_valid_from  as valid_from,
    dbt_valid_to    as valid_to,
    (dbt_valid_to is null) as is_current
from {{ ref('patient_snapshot') }}
