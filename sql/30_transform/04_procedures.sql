-- Phase 3 · Stored procedures = the single source of truth for the transform logic.
-- Both the one-shot backfill (05) and the Task DAG (06) call these, so the STAGING/MARTS
-- rules exist in exactly one place. Flatten/dedup live in the staging views (01); region,
-- SCD2, and the fact join live here.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

-- Incremental stage: consume the RAW streams, then apply the canonical views to just the
-- new keys. Consuming the streams (via the temp tables) advances their offsets, which is
-- what resets the task's WHEN gate.
CREATE OR REPLACE PROCEDURE sp_ingest()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
  CREATE OR REPLACE TEMPORARY TABLE _pat_keys AS
    SELECT patient_id FROM &{sf_database}.&{sf_schema_raw}.str_patients WHERE METADATA$ACTION = 'INSERT';
  MERGE INTO &{sf_database}.&{sf_schema_staging}.patients t
  USING (SELECT * FROM &{sf_database}.&{sf_schema_staging}.v_patients_dedup
         WHERE patient_id IN (SELECT patient_id FROM _pat_keys)) s
    ON t.patient_id = s.patient_id
  WHEN MATCHED THEN UPDATE SET first_name=s.first_name, last_name=s.last_name,
    birth_date=s.birth_date, gender=s.gender, city=s.city, state=s.state,
    ssn_masked=s.ssn_masked, phone_masked=s.phone_masked
  WHEN NOT MATCHED THEN INSERT (patient_id, first_name, last_name, birth_date, gender, city, state, ssn_masked, phone_masked)
    VALUES (s.patient_id, s.first_name, s.last_name, s.birth_date, s.gender, s.city, s.state, s.ssn_masked, s.phone_masked);

  CREATE OR REPLACE TEMPORARY TABLE _enc_keys AS
    SELECT v:encounter_id::string AS encounter_id
    FROM &{sf_database}.&{sf_schema_raw}.str_encounters WHERE METADATA$ACTION = 'INSERT';
  MERGE INTO &{sf_database}.&{sf_schema_staging}.encounters t
  USING (SELECT * FROM &{sf_database}.&{sf_schema_staging}.v_encounters_flat
         WHERE encounter_id IN (SELECT encounter_id FROM _enc_keys)) s
    ON t.encounter_id = s.encounter_id
  WHEN NOT MATCHED THEN INSERT (encounter_id, patient_id, started_at, stopped_at, encounter_class,
    provider_name, facility_id, facility_name, city, state, duration_minutes, observation_count, condition_count)
    VALUES (s.encounter_id, s.patient_id, s.started_at, s.stopped_at, s.encounter_class,
    s.provider_name, s.facility_id, s.facility_name, s.city, s.state, s.duration_minutes, s.observation_count, s.condition_count);

  INSERT INTO &{sf_database}.&{sf_schema_staging}.observations
    SELECT * FROM &{sf_database}.&{sf_schema_staging}.v_observations_flat
    WHERE encounter_id IN (SELECT encounter_id FROM _enc_keys);

  RETURN 'sp_ingest: staged stream deltas';
END;
$$;

-- Rebuild the marts from STAGING. Idempotent (MERGE / SCD2 expire-then-insert), so it is
-- safe to call after every ingest. Region, SCD2, and the fact join are defined ONLY here.
CREATE OR REPLACE PROCEDURE sp_build_marts()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_date t USING (
    SELECT TO_NUMBER(TO_CHAR(d,'YYYYMMDD')) date_key, d full_date,
           YEAR(d) year, MONTH(d) month, DAY(d) day, MONTHNAME(d) month_name, DAYOFWEEK(d) day_of_week
    FROM (SELECT DATEADD(day, SEQ4(), '2023-01-01'::date) d FROM TABLE(GENERATOR(ROWCOUNT => 1461)))
    WHERE d <= '2026-12-31'::date
  ) s ON t.date_key = s.date_key
  WHEN NOT MATCHED THEN INSERT (date_key, full_date, year, month, day, month_name, day_of_week)
    VALUES (s.date_key, s.full_date, s.year, s.month, s.day, s.month_name, s.day_of_week);

  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_location t USING (
    SELECT DISTINCT city, state,
      CASE WHEN state IN ('NY','NJ','CT','MA','PA') THEN 'Northeast'
           WHEN state IN ('CA','WA','OR') THEN 'West'
           WHEN state IN ('TX') THEN 'South'
           WHEN state IN ('IL') THEN 'Midwest' ELSE 'Other' END region
    FROM &{sf_database}.&{sf_schema_staging}.encounters
  ) s ON t.city = s.city AND t.state = s.state
  WHEN NOT MATCHED THEN INSERT (city, state, region) VALUES (s.city, s.state, s.region);

  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_facility t USING (
    SELECT DISTINCT e.facility_id, e.facility_name, l.location_sk
    FROM &{sf_database}.&{sf_schema_staging}.encounters e
    JOIN &{sf_database}.&{sf_schema_marts}.dim_location l ON l.city = e.city AND l.state = e.state
  ) s ON t.facility_id = s.facility_id
  WHEN NOT MATCHED THEN INSERT (facility_id, facility_name, location_sk)
    VALUES (s.facility_id, s.facility_name, s.location_sk);

  MERGE INTO &{sf_database}.&{sf_schema_marts}.dim_provider t USING (
    SELECT DISTINCT provider_name FROM &{sf_database}.&{sf_schema_staging}.encounters
  ) s ON t.provider_name = s.provider_name
  WHEN NOT MATCHED THEN INSERT (provider_name) VALUES (s.provider_name);

  -- SCD2 patient: expire changed current versions, then insert new versions.
  UPDATE &{sf_database}.&{sf_schema_marts}.dim_patient d
  SET valid_to = CURRENT_TIMESTAMP(), is_current = FALSE
  FROM &{sf_database}.&{sf_schema_staging}.patients s
  WHERE d.patient_id = s.patient_id AND d.is_current = TRUE
    AND (d.city <> s.city OR d.state <> s.state OR d.first_name <> s.first_name
         OR d.last_name <> s.last_name OR d.gender <> s.gender
         OR COALESCE(d.birth_date,'1900-01-01') <> COALESCE(s.birth_date,'1900-01-01'));

  INSERT INTO &{sf_database}.&{sf_schema_marts}.dim_patient
    (patient_id, first_name, last_name, birth_date, gender, city, state, valid_from, valid_to, is_current)
  SELECT s.patient_id, s.first_name, s.last_name, s.birth_date, s.gender, s.city, s.state,
    CASE WHEN EXISTS (SELECT 1 FROM &{sf_database}.&{sf_schema_marts}.dim_patient d2 WHERE d2.patient_id = s.patient_id)
         THEN CURRENT_TIMESTAMP() ELSE '1900-01-01'::timestamp_ntz END,
    NULL, TRUE
  FROM &{sf_database}.&{sf_schema_staging}.patients s
  LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_patient d
    ON d.patient_id = s.patient_id AND d.is_current = TRUE
  WHERE d.patient_id IS NULL;

  -- Fact: insert new encounters, joining the SCD2 patient version valid at encounter time.
  MERGE INTO &{sf_database}.&{sf_schema_marts}.fact_encounter t USING (
    SELECT e.encounter_id,
      TO_NUMBER(TO_CHAR(e.started_at::date,'YYYYMMDD')) date_key,
      p.patient_sk, pr.provider_sk, f.facility_sk,
      e.encounter_class, e.duration_minutes, e.observation_count, e.condition_count
    FROM &{sf_database}.&{sf_schema_staging}.encounters e
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_patient p
      ON p.patient_id = e.patient_id AND e.started_at >= p.valid_from
     AND (e.started_at < p.valid_to OR p.valid_to IS NULL)
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_provider pr ON pr.provider_name = e.provider_name
    LEFT JOIN &{sf_database}.&{sf_schema_marts}.dim_facility  f ON f.facility_id    = e.facility_id
  ) s ON t.encounter_id = s.encounter_id
  WHEN NOT MATCHED THEN INSERT
    (encounter_id, date_key, patient_sk, provider_sk, facility_sk, encounter_class, duration_minutes, observation_count, condition_count)
    VALUES (s.encounter_id, s.date_key, s.patient_sk, s.provider_sk, s.facility_sk, s.encounter_class, s.duration_minutes, s.observation_count, s.condition_count);

  RETURN 'sp_build_marts: marts refreshed';
END;
$$;