-- Phase 1 · S3 storage integration. Idempotent.
--
-- ASSUMPTION: an AWS IAM role exists that Snowflake's integration is allowed to assume
-- (trust established via the integration's IAM user ARN + external ID). Fill
-- SF_S3_URL and SF_STORAGE_AWS_ROLE_ARN in config/pipeline.conf first.
-- Full AWS walk-through: docs/snowpipe-setup.md.

USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS &{sf_storage_integration}
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '&{sf_storage_aws_role_arn}'
  STORAGE_ALLOWED_LOCATIONS = ('&{sf_s3_url}')
  COMMENT = 'S3 access for Snowpipe auto-ingest (Phase 1)';

GRANT USAGE ON INTEGRATION &{sf_storage_integration} TO ROLE &{sf_role};

-- WHY: the AWS trust policy needs the integration's generated principal + external ID.
-- Run this, copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into the IAM role
-- trust relationship (see docs/snowpipe-setup.md), then the stage below can read S3.
DESC INTEGRATION &{sf_storage_integration};
