-- Fully-in-Snowflake data governance: native Dynamic Data Masking + RBAC.
-- PII is stored as-is in RAW and masked at query time by policy. Only PII_READER sees clear;
-- every other role sees masked. This is enforced by Snowflake, not the app.

USE ROLE ACCOUNTADMIN;

CREATE SCHEMA IF NOT EXISTS &{sf_database}.GOV
  COMMENT = 'Governance objects: masking policies + transfer/audit log';
GRANT USAGE ON SCHEMA &{sf_database}.GOV TO ROLE &{sf_role};
GRANT SELECT, INSERT ON FUTURE TABLES IN SCHEMA &{sf_database}.GOV TO ROLE &{sf_role};
GRANT CREATE TABLE ON SCHEMA &{sf_database}.GOV TO ROLE &{sf_role};

-- A role authorized to read unmasked PII (everyone else is masked).
CREATE ROLE IF NOT EXISTS PII_READER COMMENT = 'Authorized to view unmasked PII';
GRANT ROLE PII_READER TO ROLE SYSADMIN;
SET deploying_user = CURRENT_USER();
GRANT ROLE PII_READER TO USER IDENTIFIER($deploying_user);

USE SCHEMA &{sf_database}.GOV;

CREATE MASKING POLICY IF NOT EXISTS mask_ssn AS (val STRING) RETURNS STRING ->
  CASE WHEN CURRENT_ROLE() = 'PII_READER' THEN val
       WHEN val IS NULL THEN NULL
       WHEN LENGTH(REGEXP_REPLACE(val,'[^0-9]','')) < 4 THEN 'XXX-XX-XXXX'
       ELSE 'XXX-XX-' || RIGHT(REGEXP_REPLACE(val,'[^0-9]',''),4) END;

CREATE MASKING POLICY IF NOT EXISTS mask_phone AS (val STRING) RETURNS STRING ->
  CASE WHEN CURRENT_ROLE() = 'PII_READER' THEN val
       WHEN val IS NULL THEN NULL
       WHEN LENGTH(REGEXP_REPLACE(val,'[^0-9]','')) < 4 THEN '(XXX) XXX-XXXX'
       ELSE '(XXX) XXX-' || RIGHT(REGEXP_REPLACE(val,'[^0-9]',''),4) END;

-- Apply to the RAW landing columns. Downstream selects inherit the policy by role.
ALTER TABLE &{sf_database}.RAW.PATIENTS_CSV MODIFY COLUMN ssn   SET MASKING POLICY GOV.mask_ssn;
ALTER TABLE &{sf_database}.RAW.PATIENTS_CSV MODIFY COLUMN phone SET MASKING POLICY GOV.mask_phone;
