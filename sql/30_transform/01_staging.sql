-- Phase 3 · STAGING tables (cleansed, typed, flattened). DDL only, idempotent.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

CREATE TABLE IF NOT EXISTS patients (
  patient_id  STRING,
  first_name  STRING,
  last_name   STRING,
  birth_date  DATE,
  gender      STRING,
  city        STRING,
  state       STRING,
  ssn_masked  STRING,          -- already masked in RAW; carried for lineage
  phone_masked STRING,
  _loaded_at  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS encounters (
  encounter_id     STRING,
  patient_id       STRING,
  started_at       TIMESTAMP_NTZ,
  stopped_at       TIMESTAMP_NTZ,
  encounter_class  STRING,
  provider_name    STRING,
  facility_id      STRING,
  facility_name    STRING,
  city             STRING,
  state            STRING,
  duration_minutes NUMBER,
  observation_count NUMBER,
  condition_count   NUMBER,
  payer            STRING,
  total_charge     NUMBER(12,2),
  paid_amount      NUMBER(12,2),
  claim_status     STRING
);

CREATE TABLE IF NOT EXISTS observations (
  encounter_id    STRING,
  obs_code        STRING,
  obs_description STRING,
  obs_value       FLOAT,
  obs_units       STRING
);

-- ---------- Canonical transform expressions (defined ONCE, here) ----------
-- Every flatten/dedup rule lives in a view so the backfill and the incremental
-- procedure reference the same definition. Changing a rule = editing one place.

CREATE OR REPLACE VIEW v_patients_dedup AS
SELECT patient_id, first_name, last_name, birth_date, gender, city, state,
       mask_ssn(ssn) AS ssn_masked, mask_phone(phone) AS phone_masked
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY _load_ts DESC NULLS LAST) rn
  FROM &{sf_database}.&{sf_schema_raw}.patients_csv
) WHERE rn = 1;

CREATE OR REPLACE VIEW v_encounters_flat AS
SELECT
  v:encounter_id::string           AS encounter_id,
  v:patient_id::string             AS patient_id,
  v:start::timestamp_ntz           AS started_at,
  v:stop::timestamp_ntz            AS stopped_at,
  v:encounter_class::string        AS encounter_class,
  v:provider.name::string          AS provider_name,
  v:provider.facility_id::string   AS facility_id,
  v:provider.facility_name::string AS facility_name,
  v:provider.city::string          AS city,
  v:provider.state::string         AS state,
  DATEDIFF('minute', v:start::timestamp_ntz, v:stop::timestamp_ntz) AS duration_minutes,
  ARRAY_SIZE(v:observations)       AS observation_count,
  ARRAY_SIZE(v:conditions)         AS condition_count,
  v:billing.payer::string          AS payer,
  v:billing.total_charge::number(12,2) AS total_charge,
  v:billing.paid_amount::number(12,2)  AS paid_amount,
  v:billing.claim_status::string   AS claim_status
FROM &{sf_database}.&{sf_schema_raw}.encounters_json;

CREATE OR REPLACE VIEW v_observations_flat AS
SELECT
  e.v:encounter_id::string        AS encounter_id,
  obs.value:code::string          AS obs_code,
  obs.value:description::string   AS obs_description,
  obs.value:value::float          AS obs_value,
  obs.value:units::string         AS obs_units
FROM &{sf_database}.&{sf_schema_raw}.encounters_json e,
     LATERAL FLATTEN(input => e.v:observations) obs;
