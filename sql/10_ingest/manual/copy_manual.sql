-- Phase 1 · Manual COPY INTO fallback (troubleshooting).
-- Bypasses Snowpipe/SQS to load whatever is already staged in S3. Use when auto-ingest
-- looks stuck: it surfaces load errors synchronously instead of in PIPE history.

USE ROLE &{sf_role};
USE WAREHOUSE &{sf_warehouse};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

LIST @&{sf_stage};

COPY INTO patients_csv
FROM @&{sf_stage}
FILE_FORMAT = (FORMAT_NAME = csv_format)
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
INCLUDE_METADATA = (_source_file = METADATA$FILENAME)
PATTERN = '.*patients.*[.]csv'
ON_ERROR = 'CONTINUE';

COPY INTO encounters_json (v, _source_file, _file_row)
FROM (
  SELECT $1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
  FROM @&{sf_stage}
)
FILE_FORMAT = (FORMAT_NAME = json_format)
PATTERN = '.*encounters.*[.]json'
ON_ERROR = 'CONTINUE';

-- Diagnose a single bad file without loading it:
--   COPY INTO patients_csv FROM @&{sf_stage}
--   FILE_FORMAT = (FORMAT_NAME = csv_format)
--   PATTERN = '.*patients.*[.]csv'
--   VALIDATION_MODE = 'RETURN_ERRORS';
