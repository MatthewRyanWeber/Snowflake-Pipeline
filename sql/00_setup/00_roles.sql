-- Phase 0 · RBAC bootstrap. Idempotent: safe to re-run.
--
-- ASSUMPTION: the deploying user holds ACCOUNTADMIN (the Snowflake trial default),
-- which lets it activate USERADMIN / SECURITYADMIN through the role hierarchy.
-- On a non-trial account, grant those roles to the deployer first.

USE ROLE USERADMIN;

-- WHY: a dedicated functional role keeps pipeline objects out of ACCOUNTADMIN and
-- gives interviewers a clean least-privilege story.
CREATE ROLE IF NOT EXISTS &{sf_role}
  COMMENT = 'Functional role owning the Snowflake analytics pipeline';

USE ROLE SECURITYADMIN;

-- WHY: parent the role under SYSADMIN so account admins inherit pipeline access.
GRANT ROLE &{sf_role} TO ROLE SYSADMIN;

-- WHY: let the human deployer activate the role in their own session without a re-login.
SET deploying_user = CURRENT_USER();
GRANT ROLE &{sf_role} TO USER IDENTIFIER($deploying_user);
