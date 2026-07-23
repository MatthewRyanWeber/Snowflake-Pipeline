-- Phase 3 · Streams capture change on RAW so downstream loads are incremental. Idempotent.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

-- APPEND_ONLY streams: RAW is insert-only (Snowpipe/loader append), so we only need inserts.
CREATE STREAM IF NOT EXISTS str_patients
  ON TABLE patients_csv
  APPEND_ONLY = TRUE
  COMMENT = 'New patient rows to propagate into STAGING/DIM_PATIENT';

CREATE STREAM IF NOT EXISTS str_encounters
  ON TABLE encounters_json
  APPEND_ONLY = TRUE
  COMMENT = 'New encounter rows to flatten into STAGING';
