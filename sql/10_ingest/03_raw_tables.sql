-- Phase 1 · RAW target tables. Idempotent.
-- RAW stays close to source: CSV → typed columns, JSON → a single VARIANT.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

-- Structured / relational source.
CREATE TABLE IF NOT EXISTS patients_csv (
  patient_id   STRING,
  first_name   STRING,
  last_name    STRING,
  birth_date   DATE,
  gender       STRING,
  ssn          STRING,          -- PII: masked downstream in STAGING (Phase 2/3)
  address      STRING,
  city         STRING,
  state        STRING,
  zip          STRING,
  phone        STRING,          -- PII: masked downstream
  _source_file STRING,
  _load_ts     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Semi-structured / "NoSQL" source — the VARIANT demonstration.
CREATE TABLE IF NOT EXISTS encounters_json (
  v            VARIANT,
  _source_file STRING,
  _file_row    NUMBER,
  _load_ts     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
