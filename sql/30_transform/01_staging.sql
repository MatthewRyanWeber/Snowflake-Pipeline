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
  condition_count   NUMBER
);

CREATE TABLE IF NOT EXISTS observations (
  encounter_id    STRING,
  obs_code        STRING,
  obs_description STRING,
  obs_value       FLOAT,
  obs_units       STRING
);
