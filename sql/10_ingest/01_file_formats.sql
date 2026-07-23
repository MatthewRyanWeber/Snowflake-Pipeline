-- Phase 1 · File formats. Idempotent (non-destructive IF NOT EXISTS).

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

-- PARSE_HEADER lets COPY match columns by NAME (MATCH_BY_COLUMN_NAME), so loads don't
-- depend on column order. Re-runnable via CREATE OR REPLACE.
CREATE OR REPLACE FILE FORMAT csv_format
  TYPE = CSV
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  PARSE_HEADER = TRUE
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
  NULL_IF = ('', 'NULL')
  EMPTY_FIELD_AS_NULL = TRUE
  COMMENT = 'patients.csv — header parsed for name-based column matching';

CREATE FILE FORMAT IF NOT EXISTS json_format
  TYPE = JSON
  STRIP_OUTER_ARRAY = FALSE
  COMMENT = 'encounters.json — NDJSON, one object per line';
