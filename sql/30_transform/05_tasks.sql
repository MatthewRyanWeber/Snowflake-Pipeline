-- Phase 3 · Task DAG: root + dependent tasks, stream-driven, scheduled.
-- Backfill (04) seeds the model from existing RAW; this DAG keeps it current from the
-- STREAMS as new rows arrive. Each task is a single statement (one stream consumed once).
-- Every task pins WAREHOUSE = PIPELINE_WH (warehouse-backed, not serverless) so only
-- EXECUTE TASK is required. Re-runnable: the graph is suspended, replaced, then resumed.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

-- Suspend the whole graph before replacing (root first — a graph can't be altered while
-- its root is resumed). IF EXISTS makes the first run a no-op.
ALTER TASK IF EXISTS t_stage_patients SUSPEND;
ALTER TASK IF EXISTS t_land_encounters SUSPEND;
ALTER TASK IF EXISTS t_stage_encounters SUSPEND;
ALTER TASK IF EXISTS t_stage_observations SUSPEND;
ALTER TASK IF EXISTS t_dim_location SUSPEND;
ALTER TASK IF EXISTS t_dim_facility SUSPEND;
ALTER TASK IF EXISTS t_dim_provider SUSPEND;
ALTER TASK IF EXISTS t_scd2_expire SUSPEND;
ALTER TASK IF EXISTS t_scd2_insert SUSPEND;
ALTER TASK IF EXISTS t_fact SUSPEND;

-- Delta buffer: the encounter stream is consumed once into here, then two tasks
-- (encounters + observations) read the same delta.
CREATE TABLE IF NOT EXISTS encounters_delta (v VARIANT);

-- ---------- ROOT ----------
CREATE OR REPLACE TASK t_stage_patients
  WAREHOUSE = &{sf_warehouse}
  SCHEDULE = '1 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('&{sf_database}.&{sf_schema_raw}.str_patients')
    OR SYSTEM$STREAM_HAS_DATA('&{sf_database}.&{sf_schema_raw}.str_encounters')
AS
  MERGE INTO staging.patients t USING (
    SELECT patient_id, first_name, last_name, birth_date, gender, city, state, ssn, phone
    FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY _load_ts DESC) rn
          FROM &{sf_database}.&{sf_schema_raw}.str_patients WHERE METADATA$ACTION = 'INSERT')
    WHERE rn = 1
  ) s ON t.patient_id = s.patient_id
  WHEN MATCHED THEN UPDATE SET first_name=s.first_name, last_name=s.last_name,
    birth_date=s.birth_date, gender=s.gender, city=s.city, state=s.state,
    ssn_masked=s.ssn, phone_masked=s.phone
  WHEN NOT MATCHED THEN INSERT (patient_id, first_name, last_name, birth_date, gender, city, state, ssn_masked, phone_masked)
    VALUES (s.patient_id, s.first_name, s.last_name, s.birth_date, s.gender, s.city, s.state, s.ssn, s.phone);

-- ---------- STAGING (dependent) ----------
CREATE OR REPLACE TASK t_land_encounters
  WAREHOUSE = &{sf_warehouse} AFTER t_stage_patients AS
  INSERT OVERWRITE INTO staging.encounters_delta (v)
  SELECT v FROM &{sf_database}.&{sf_schema_raw}.str_encounters WHERE METADATA$ACTION = 'INSERT';

CREATE OR REPLACE TASK t_stage_encounters
  WAREHOUSE = &{sf_warehouse} AFTER t_land_encounters AS
  MERGE INTO staging.encounters t USING (
    SELECT v:encounter_id::string encounter_id, v:patient_id::string patient_id,
           v:start::timestamp_ntz started_at, v:stop::timestamp_ntz stopped_at,
           v:encounter_class::string encounter_class, v:provider.name::string provider_name,
           v:provider.facility_id::string facility_id, v:provider.facility_name::string facility_name,
           v:provider.city::string city, v:provider.state::string state,
           DATEDIFF('minute', v:start::timestamp_ntz, v:stop::timestamp_ntz) duration_minutes,
           ARRAY_SIZE(v:observations) observation_count, ARRAY_SIZE(v:conditions) condition_count
    FROM staging.encounters_delta
  ) s ON t.encounter_id = s.encounter_id
  WHEN NOT MATCHED THEN INSERT VALUES (s.encounter_id, s.patient_id, s.started_at, s.stopped_at,
    s.encounter_class, s.provider_name, s.facility_id, s.facility_name, s.city, s.state,
    s.duration_minutes, s.observation_count, s.condition_count);

CREATE OR REPLACE TASK t_stage_observations
  WAREHOUSE = &{sf_warehouse} AFTER t_stage_encounters AS
  INSERT INTO staging.observations
  SELECT e.v:encounter_id::string, obs.value:code::string, obs.value:description::string,
         obs.value:value::float, obs.value:units::string
  FROM staging.encounters_delta e, LATERAL FLATTEN(input => e.v:observations) obs;

-- ---------- DIMS (dependent) ----------
CREATE OR REPLACE TASK t_dim_location
  WAREHOUSE = &{sf_warehouse} AFTER t_stage_encounters AS
  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_location t USING (
    SELECT DISTINCT city, state,
      CASE WHEN state IN ('NY','NJ','CT','MA','PA') THEN 'Northeast'
           WHEN state IN ('CA','WA','OR') THEN 'West'
           WHEN state IN ('TX') THEN 'South'
           WHEN state IN ('IL') THEN 'Midwest' ELSE 'Other' END region
    FROM staging.encounters
  ) s ON t.city = s.city AND t.state = s.state
  WHEN NOT MATCHED THEN INSERT (city, state, region) VALUES (s.city, s.state, s.region);

CREATE OR REPLACE TASK t_dim_facility
  WAREHOUSE = &{sf_warehouse} AFTER t_dim_location AS
  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_facility t USING (
    SELECT DISTINCT e.facility_id, e.facility_name, l.location_sk
    FROM staging.encounters e
    JOIN &{sf_database}.&{sf_schema_marts}.dim_location l ON l.city = e.city AND l.state = e.state
  ) s ON t.facility_id = s.facility_id
  WHEN NOT MATCHED THEN INSERT (facility_id, facility_name, location_sk)
    VALUES (s.facility_id, s.facility_name, s.location_sk);

CREATE OR REPLACE TASK t_dim_provider
  WAREHOUSE = &{sf_warehouse} AFTER t_stage_encounters AS
  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_provider t USING (
    SELECT DISTINCT provider_name FROM staging.encounters
  ) s ON t.provider_name = s.provider_name
  WHEN NOT MATCHED THEN INSERT (provider_name) VALUES (s.provider_name);

-- ---------- SCD2 patient (dependent) ----------
CREATE OR REPLACE TASK t_scd2_expire
  WAREHOUSE = &{sf_warehouse} AFTER t_stage_patients AS
  UPDATE &{sf_database}.&{sf_schema_marts}.dim_patient d
  SET valid_to = CURRENT_TIMESTAMP(), is_current = FALSE
  FROM staging.patients s
  WHERE d.patient_id = s.patient_id AND d.is_current = TRUE
    AND (d.city <> s.city OR d.state <> s.state OR d.first_name <> s.first_name
         OR d.last_name <> s.last_name OR d.gender <> s.gender
         OR COALESCE(d.birth_date,'1900-01-01') <> COALESCE(s.birth_date,'1900-01-01'));

CREATE OR REPLACE TASK t_scd2_insert
  WAREHOUSE = &{sf_warehouse} AFTER t_scd2_expire AS
  INSERT INTO &{sf_database}.&{sf_schema_marts}.dim_patient
    (patient_id, first_name, last_name, birth_date, gender, city, state, valid_from, valid_to, is_current)
  SELECT s.patient_id, s.first_name, s.last_name, s.birth_date, s.gender, s.city, s.state,
    CASE WHEN EXISTS (SELECT 1 FROM &{sf_database}.&{sf_schema_marts}.dim_patient d2 WHERE d2.patient_id = s.patient_id)
         THEN CURRENT_TIMESTAMP() ELSE '1900-01-01'::timestamp_ntz END,
    NULL, TRUE
  FROM staging.patients s
  LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_patient d
    ON d.patient_id = s.patient_id AND d.is_current = TRUE
  WHERE d.patient_id IS NULL;

-- ---------- FACT (finalizer, multiple predecessors) ----------
CREATE OR REPLACE TASK t_fact
  WAREHOUSE = &{sf_warehouse}
  AFTER t_stage_encounters, t_stage_observations, t_dim_facility, t_dim_provider, t_scd2_insert
AS
  MERGE INTO &{sf_database}.&{sf_schema_marts}.fact_encounter t USING (
    SELECT e.encounter_id,
      TO_NUMBER(TO_CHAR(e.started_at::date,'YYYYMMDD')) date_key,
      p.patient_sk, pr.provider_sk, f.facility_sk,
      e.encounter_class, e.duration_minutes, e.observation_count, e.condition_count
    FROM staging.encounters e
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_patient p
      ON p.patient_id = e.patient_id AND e.started_at >= p.valid_from
     AND (e.started_at < p.valid_to OR p.valid_to IS NULL)
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_provider pr ON pr.provider_name = e.provider_name
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_facility  f ON f.facility_id    = e.facility_id
  ) s ON t.encounter_id = s.encounter_id
  WHEN NOT MATCHED THEN INSERT
    (encounter_id, date_key, patient_sk, provider_sk, facility_sk, encounter_class, duration_minutes, observation_count, condition_count)
    VALUES (s.encounter_id, s.date_key, s.patient_sk, s.provider_sk, s.facility_sk, s.encounter_class, s.duration_minutes, s.observation_count, s.condition_count);

-- ---------- Activate: resume dependents first, then the root (root last enables schedule) ----------
ALTER TASK t_fact RESUME;
ALTER TASK t_scd2_insert RESUME;
ALTER TASK t_scd2_expire RESUME;
ALTER TASK t_dim_provider RESUME;
ALTER TASK t_dim_facility RESUME;
ALTER TASK t_dim_location RESUME;
ALTER TASK t_stage_observations RESUME;
ALTER TASK t_stage_encounters RESUME;
ALTER TASK t_land_encounters RESUME;
ALTER TASK t_stage_patients RESUME;
