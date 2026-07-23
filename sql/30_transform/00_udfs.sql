-- Phase 3 · In-warehouse PII masking UDFs (governance).
-- The staging views call these so masking is enforced inside Snowflake as well as on load.
-- Idempotent: re-masking an already-masked value returns the same value.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

CREATE OR REPLACE FUNCTION mask_ssn(val STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
  CASE WHEN val IS NULL THEN NULL
       WHEN val = '' THEN ''
       ELSE 'XXX-XX-' || RIGHT(REGEXP_REPLACE(val, '[^0-9]', ''), 4)
  END
$$;

CREATE OR REPLACE FUNCTION mask_phone(val STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
  CASE WHEN val IS NULL THEN NULL
       WHEN val = '' THEN ''
       ELSE '(XXX) XXX-' || RIGHT(REGEXP_REPLACE(val, '[^0-9]', ''), 4)
  END
$$;
