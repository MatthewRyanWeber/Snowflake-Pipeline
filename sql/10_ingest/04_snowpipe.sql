-- Phase 1 · Snowpipe auto-ingest pipes. Idempotent.
--
-- After creating, run `SHOW PIPES;` and copy each pipe's `notification_channel`
-- (the SQS ARN) into the S3 bucket's event notification so new files auto-load.
-- See docs/snowpipe-setup.md.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

CREATE PIPE IF NOT EXISTS patients_pipe
  AUTO_INGEST = TRUE
  COMMENT = 'Auto-ingest patients CSV'
  AS
  COPY INTO patients_csv
  FROM @&{sf_stage}
  FILE_FORMAT = (FORMAT_NAME = csv_format)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE          -- name-based; order-independent
  INCLUDE_METADATA = (_source_file = METADATA$FILENAME)
  PATTERN = '.*patients.*[.]csv';

CREATE PIPE IF NOT EXISTS encounters_pipe
  AUTO_INGEST = TRUE
  COMMENT = 'Auto-ingest encounters NDJSON'
  AS
  COPY INTO encounters_json (v, _source_file, _file_row)
  FROM (
    SELECT $1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
    FROM @&{sf_stage}
  )
  FILE_FORMAT = (FORMAT_NAME = json_format)
  PATTERN = '.*encounters.*[.]json';

SHOW PIPES IN SCHEMA &{sf_database}.&{sf_schema_raw};
