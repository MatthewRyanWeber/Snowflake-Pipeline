-- Metadata-driven ingestion: the pipeline's work-list lives in a control TABLE, not code.
-- Adding a table to the pipeline is an INSERT here; the loader reads its table list from this.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.GOV;

CREATE TABLE IF NOT EXISTS sources (
  source_group  STRING,                 -- which load run this belongs to (matches the config)
  source_table  STRING,                 -- table name in the source system
  target_table  STRING,                 -- RAW target in Snowflake
  hwm_column    STRING,                 -- high-water-mark column for incremental loads
  batch_size    NUMBER DEFAULT 5000,
  mask          VARIANT,                -- optional {"col":"policy"}; NULL = native policy governs
  enabled       BOOLEAN DEFAULT TRUE,
  updated_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT uq_sources UNIQUE (source_group, source_table)
);

-- Seed one entry (idempotent).
INSERT INTO sources (source_group, source_table, target_table, hwm_column, batch_size, mask, enabled)
SELECT 'sqlserver_health', 'patients', 'PATIENTS_CSV', 'patient_id', 5000, NULL, TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM sources WHERE source_group = 'sqlserver_health' AND source_table = 'patients'
);
