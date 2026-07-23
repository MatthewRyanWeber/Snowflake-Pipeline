-- Scaling + operations: cost guardrail, tag-based masking, load-health view, failure alert.

-- 1) Resource monitor: cap credits, notify + suspend before a runaway load drains the account.
USE ROLE ACCOUNTADMIN;
CREATE RESOURCE MONITOR IF NOT EXISTS pipeline_rm
  WITH CREDIT_QUOTA = 50
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 75 PERCENT DO NOTIFY
           ON 90 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND
           ON 110 PERCENT DO SUSPEND_IMMEDIATE;
ALTER WAREHOUSE &{sf_warehouse} SET RESOURCE_MONITOR = pipeline_rm;

-- 2) Tag-based masking: define policy+tag once; tagging any new PII column auto-masks it.
USE SCHEMA &{sf_database}.GOV;
CREATE TAG IF NOT EXISTS pii COMMENT = 'Marks PII columns for automatic masking';
CREATE MASKING POLICY IF NOT EXISTS mask_tagged AS (val STRING) RETURNS STRING ->
  CASE WHEN CURRENT_ROLE() = 'PII_READER' THEN val
       WHEN val IS NULL THEN NULL
       ELSE '***MASKED***' END;
ALTER TAG pii SET MASKING POLICY mask_tagged;
-- Governance now scales by tagging (here: address becomes masked with one statement).
ALTER TABLE &{sf_database}.RAW.PATIENTS_CSV MODIFY COLUMN address SET TAG GOV.pii = 'address';

-- Privileges so the pipeline role can own the alert.
GRANT EXECUTE ALERT ON ACCOUNT TO ROLE &{sf_role};
GRANT CREATE ALERT ON SCHEMA &{sf_database}.GOV TO ROLE &{sf_role};
GRANT CREATE VIEW ON SCHEMA &{sf_database}.GOV TO ROLE &{sf_role};

-- 3) Load-health view + 4) task-failure alert.
USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.GOV;

CREATE OR REPLACE VIEW vw_pipeline_health AS
SELECT target,
       COUNT(*)               AS loads,
       SUM(rows_written)      AS total_rows_written,
       MAX(loaded_at)         AS last_loaded_at,
       MAX_BY(loaded_by, loaded_at) AS last_loaded_by
FROM gov.load_log
GROUP BY target;

CREATE TABLE IF NOT EXISTS alert_log (
  alerted_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  message    STRING
);

CREATE OR REPLACE ALERT task_failure_alert
  WAREHOUSE = &{sf_warehouse}
  SCHEDULE = '5 MINUTE'
  IF (EXISTS (
    SELECT 1 FROM TABLE(&{sf_database}.INFORMATION_SCHEMA.TASK_HISTORY(
      SCHEDULED_TIME_RANGE_START => DATEADD('minute', -10, CURRENT_TIMESTAMP())))
    WHERE STATE = 'FAILED'))
  THEN INSERT INTO gov.alert_log(message)
       SELECT 'Task failure detected in the last 10 minutes';
ALTER ALERT task_failure_alert RESUME;
