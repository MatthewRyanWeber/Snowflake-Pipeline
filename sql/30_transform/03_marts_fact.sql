-- Phase 3 · FACT_ENCOUNTER. DDL only, idempotent.
-- Grain: one row per encounter. Foreign keys to the conformed dimensions; the facility
-- FK reaches location through DIM_FACILITY (the snowflake arm).

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_marts};

CREATE TABLE IF NOT EXISTS fact_encounter (
  encounter_id      STRING,                 -- degenerate dimension (natural key)
  date_key          NUMBER REFERENCES dim_date(date_key),
  patient_sk        NUMBER REFERENCES dim_patient(patient_sk),
  provider_sk       NUMBER REFERENCES dim_provider(provider_sk),
  facility_sk       NUMBER REFERENCES dim_facility(facility_sk),
  encounter_class   STRING,
  -- measures
  duration_minutes  NUMBER,
  observation_count NUMBER,
  condition_count   NUMBER,
  _built_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
