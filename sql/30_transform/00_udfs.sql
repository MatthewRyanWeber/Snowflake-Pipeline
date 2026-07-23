-- Phase 3 · In-warehouse PII masking UDFs (governance).
-- The staging views call these so masking is enforced inside Snowflake as well as on load.
-- Logic matches loader/masking.py: NULL->NULL, ''->'', <4 digits->placeholder, else last 4.
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
       WHEN LENGTH(REGEXP_REPLACE(val, '[^0-9]', '')) < 4 THEN 'XXX-XX-XXXX'
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
       WHEN LENGTH(REGEXP_REPLACE(val, '[^0-9]', '')) < 4 THEN '(XXX) XXX-XXXX'
       ELSE '(XXX) XXX-' || RIGHT(REGEXP_REPLACE(val, '[^0-9]', ''), 4)
  END
$$;
