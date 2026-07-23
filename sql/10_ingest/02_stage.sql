-- Phase 1 · External S3 stage. Idempotent.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

CREATE STAGE IF NOT EXISTS &{sf_stage}
  URL = '&{sf_s3_url}'
  STORAGE_INTEGRATION = &{sf_storage_integration}
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'External S3 stage for health files (Phase 1)';

-- Smoke check that the integration can actually see the bucket.
LIST @&{sf_stage};
