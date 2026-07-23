-- Phase 1 · File formats. Idempotent (non-destructive IF NOT EXISTS).

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

CREATE FILE FORMAT IF NOT EXISTS csv_format
  TYPE = CSV
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  SKIP_HEADER = 1
  NULL_IF = ('', 'NULL')
  EMPTY_FIELD_AS_NULL = TRUE
  COMMENT = 'patients.csv — header row, quoted fields';

CREATE FILE FORMAT IF NOT EXISTS json_format
  TYPE = JSON
  STRIP_OUTER_ARRAY = FALSE
  COMMENT = 'encounters.json — NDJSON, one object per line';
