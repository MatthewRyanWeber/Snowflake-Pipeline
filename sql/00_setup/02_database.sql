-- Phase 0 · Database + schemas. Idempotent.

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS &{sf_database}
  COMMENT = 'Synthetic healthcare analytics pipeline (Synthea) — no real PHI';

CREATE SCHEMA IF NOT EXISTS &{sf_database}.&{sf_schema_raw}
  COMMENT = 'Landing zone — Snowpipe (files) + Python batch loader; VARIANT for JSON';
CREATE SCHEMA IF NOT EXISTS &{sf_database}.&{sf_schema_staging}
  COMMENT = 'Cleansed, typed, deduped — fed by Streams';
CREATE SCHEMA IF NOT EXISTS &{sf_database}.&{sf_schema_marts}
  COMMENT = 'Star schema — facts + conformed dims (one deliberately snowflaked)';

-- WHY: hand the whole tree to the pipeline role so it owns and manages its own objects.
-- COPY CURRENT GRANTS keeps any grants already present when re-run.
GRANT OWNERSHIP ON DATABASE &{sf_database}                     TO ROLE &{sf_role} COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   &{sf_database}.&{sf_schema_raw}     TO ROLE &{sf_role} COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   &{sf_database}.&{sf_schema_staging} TO ROLE &{sf_role} COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA   &{sf_database}.&{sf_schema_marts}   TO ROLE &{sf_role} COPY CURRENT GRANTS;
