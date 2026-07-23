-- Transfer / audit log. Each load writes a row here; Snowflake's COPY_HISTORY and
-- ACCESS_HISTORY provide the native complement.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.GOV;

CREATE TABLE IF NOT EXISTS load_log (
  log_id        NUMBER IDENTITY PRIMARY KEY,
  run_id        STRING,
  source        STRING,
  target        STRING,
  rows_read     NUMBER,
  rows_written  NUMBER,
  loaded_by     STRING,
  loaded_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
