-- Phase 3 · Task DAG: root + one dependent, each calling a shared procedure. Stream-gated,
-- scheduled. The transform logic lives in the procedures (04), not here — this file is pure
-- orchestration. Re-runnable: suspend (root first) -> replace -> resume (root last).

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

ALTER TASK IF EXISTS t_ingest SUSPEND;
ALTER TASK IF EXISTS t_build_marts SUSPEND;

-- Root: runs only when a RAW stream has new rows; sp_ingest consumes the streams.
CREATE OR REPLACE TASK t_ingest
  WAREHOUSE = &{sf_warehouse}
  SCHEDULE = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('&{sf_database}.&{sf_schema_raw}.str_patients')
    OR SYSTEM$STREAM_HAS_DATA('&{sf_database}.&{sf_schema_raw}.str_encounters')
AS
  CALL &{sf_database}.&{sf_schema_staging}.sp_ingest();

CREATE OR REPLACE TASK t_build_marts
  WAREHOUSE = &{sf_warehouse}
  AFTER t_ingest
AS
  CALL &{sf_database}.&{sf_schema_staging}.sp_build_marts();

ALTER TASK t_build_marts RESUME;   -- dependent first
ALTER TASK t_ingest RESUME;        -- root last enables the schedule
