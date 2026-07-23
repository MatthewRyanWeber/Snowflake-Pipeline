-- Fully-in-Snowflake declarative transform: Dynamic Tables.
-- Snowflake maintains these automatically on TARGET_LAG -- no external orchestration, no
-- streams/tasks/procedures to manage. PII columns materialize masked (the owner role sees
-- masked via the policy), so the analytical layer never holds raw PII.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

CREATE OR REPLACE DYNAMIC TABLE dt_patients
  TARGET_LAG = '1 minute'
  WAREHOUSE = &{sf_warehouse}
AS
  SELECT patient_id, first_name, last_name, birth_date::date AS birth_date, gender, city, state,
         ssn AS ssn_masked, phone AS phone_masked
  FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY _load_ts DESC NULLS LAST) rn
    FROM &{sf_database}.&{sf_schema_raw}.patients_csv
  ) WHERE rn = 1;

CREATE OR REPLACE DYNAMIC TABLE dt_encounters
  TARGET_LAG = '1 minute'
  WAREHOUSE = &{sf_warehouse}
AS
  SELECT v:encounter_id::string AS encounter_id, v:patient_id::string AS patient_id,
         v:start::timestamp_ntz AS started_at, v:encounter_class::string AS encounter_class,
         v:provider.name::string AS provider_name, v:provider.state::string AS state,
         v:billing.payer::string AS payer, v:billing.total_charge::number(12,2) AS total_charge
  FROM &{sf_database}.&{sf_schema_raw}.encounters_json;
