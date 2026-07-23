-- Phase 0 · Acceptance check. Activates the pipeline role and confirms the
-- role/warehouse/database/schemas resolve. Non-destructive; safe to re-run.

USE ROLE &{sf_role};
USE WAREHOUSE &{sf_warehouse};
USE DATABASE &{sf_database};

SELECT
  CURRENT_ROLE()      AS current_role,
  CURRENT_WAREHOUSE() AS current_warehouse,
  CURRENT_DATABASE()  AS current_database;

-- Expect exactly three rows: RAW, STAGING, MARTS (plus INFORMATION_SCHEMA).
SHOW SCHEMAS IN DATABASE &{sf_database};
