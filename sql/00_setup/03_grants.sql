-- Phase 0 · Operational grants. Idempotent (GRANT is naturally re-runnable).
-- The pipeline role already OWNS the schemas (02_database.sql); these make the grants
-- explicit and add FUTURE grants so objects created later are covered without edits here.

USE ROLE SYSADMIN;

GRANT USAGE ON DATABASE &{sf_database} TO ROLE &{sf_role};

-- RAW
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE STAGE, CREATE FILE FORMAT, CREATE PIPE, CREATE STREAM
  ON SCHEMA &{sf_database}.&{sf_schema_raw} TO ROLE &{sf_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA &{sf_database}.&{sf_schema_raw} TO ROLE &{sf_role};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA &{sf_database}.&{sf_schema_raw} TO ROLE &{sf_role};

-- STAGING
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE STREAM, CREATE TASK
  ON SCHEMA &{sf_database}.&{sf_schema_staging} TO ROLE &{sf_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA &{sf_database}.&{sf_schema_staging} TO ROLE &{sf_role};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA &{sf_database}.&{sf_schema_staging} TO ROLE &{sf_role};

-- MARTS
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE TASK
  ON SCHEMA &{sf_database}.&{sf_schema_marts} TO ROLE &{sf_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA &{sf_database}.&{sf_schema_marts} TO ROLE &{sf_role};
GRANT SELECT ON FUTURE VIEWS IN SCHEMA &{sf_database}.&{sf_schema_marts} TO ROLE &{sf_role};

-- WHY: Tasks run as the role that owns them; these are account-level task privileges.
-- EXECUTE TASK covers warehouse-backed tasks; EXECUTE MANAGED TASK covers serverless ones.
USE ROLE ACCOUNTADMIN;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE &{sf_role};
GRANT EXECUTE MANAGED TASK ON ACCOUNT TO ROLE &{sf_role};
