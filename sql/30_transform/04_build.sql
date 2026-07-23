-- Phase 3 · Backfill build: RAW -> STAGING -> MARTS. Idempotent (re-runnable).
-- Streams (00) handle ongoing change via tasks (05); this seeds the model from data
-- already in RAW. INSERT OVERWRITE gives an atomic, idempotent snapshot for derived tables;
-- DIM_PATIENT uses a proper SCD2 expire-then-insert.

USE ROLE &{sf_role};
USE WAREHOUSE &{sf_warehouse};
USE DATABASE &{sf_database};

-- ---------- STAGING ----------
INSERT OVERWRITE INTO staging.patients
    (patient_id, first_name, last_name, birth_date, gender, city, state, ssn_masked, phone_masked)
SELECT patient_id, first_name, last_name, birth_date, gender, city, state, ssn, phone
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY _load_ts DESC NULLS LAST) rn
  FROM raw.patients_csv
) WHERE rn = 1;

INSERT OVERWRITE INTO staging.encounters
SELECT
  v:encounter_id::string,
  v:patient_id::string,
  v:start::timestamp_ntz,
  v:stop::timestamp_ntz,
  v:encounter_class::string,
  v:provider.name::string,
  v:provider.facility_id::string,
  v:provider.facility_name::string,
  v:provider.city::string,
  v:provider.state::string,
  DATEDIFF('minute', v:start::timestamp_ntz, v:stop::timestamp_ntz),
  ARRAY_SIZE(v:observations),
  ARRAY_SIZE(v:conditions)
FROM raw.encounters_json;

INSERT OVERWRITE INTO staging.observations
SELECT
  e.v:encounter_id::string,
  obs.value:code::string,
  obs.value:description::string,
  obs.value:value::float,
  obs.value:units::string
FROM raw.encounters_json e,
     LATERAL FLATTEN(input => e.v:observations) obs;

-- ---------- MARTS: conformed dims ----------
MERGE INTO marts.dim_date t USING (
  SELECT TO_NUMBER(TO_CHAR(d,'YYYYMMDD')) date_key, d full_date,
         YEAR(d) year, MONTH(d) month, DAY(d) day, MONTHNAME(d) month_name, DAYOFWEEK(d) day_of_week
  FROM (SELECT DATEADD(day, SEQ4(), '2023-01-01'::date) d FROM TABLE(GENERATOR(ROWCOUNT => 1461)))
  WHERE d <= '2026-12-31'::date
) s ON t.date_key = s.date_key
WHEN NOT MATCHED THEN INSERT (date_key, full_date, year, month, day, month_name, day_of_week)
  VALUES (s.date_key, s.full_date, s.year, s.month, s.day, s.month_name, s.day_of_week);

-- Snowflake level 2: location -> region.
MERGE INTO marts.dim_location t USING (
  SELECT DISTINCT city, state,
    CASE WHEN state IN ('NY','NJ','CT','MA','PA') THEN 'Northeast'
         WHEN state IN ('CA','WA','OR')          THEN 'West'
         WHEN state IN ('TX')                     THEN 'South'
         WHEN state IN ('IL')                     THEN 'Midwest'
         ELSE 'Other' END AS region
  FROM staging.encounters
) s ON t.city = s.city AND t.state = s.state
WHEN NOT MATCHED THEN INSERT (city, state, region) VALUES (s.city, s.state, s.region);

-- Snowflake level 1: facility -> location.
MERGE INTO marts.dim_facility t USING (
  SELECT DISTINCT e.facility_id, e.facility_name, l.location_sk
  FROM staging.encounters e
  JOIN marts.dim_location l ON l.city = e.city AND l.state = e.state
) s ON t.facility_id = s.facility_id
WHEN NOT MATCHED THEN INSERT (facility_id, facility_name, location_sk)
  VALUES (s.facility_id, s.facility_name, s.location_sk);

MERGE INTO marts.dim_provider t USING (
  SELECT DISTINCT provider_name FROM staging.encounters
) s ON t.provider_name = s.provider_name
WHEN NOT MATCHED THEN INSERT (provider_name) VALUES (s.provider_name);

-- ---------- MARTS: SCD Type 2 patient ----------
-- Step A: expire current versions whose tracked attributes changed.
UPDATE marts.dim_patient d
SET valid_to = CURRENT_TIMESTAMP(), is_current = FALSE
FROM staging.patients s
WHERE d.patient_id = s.patient_id
  AND d.is_current = TRUE
  AND (d.city <> s.city OR d.state <> s.state OR d.first_name <> s.first_name
       OR d.last_name <> s.last_name OR d.gender <> s.gender
       OR COALESCE(d.birth_date, '1900-01-01') <> COALESCE(s.birth_date, '1900-01-01'));

-- Step B: insert a current version for brand-new patients AND just-expired ones.
-- The FIRST version of a patient opens at an epoch so historical encounters fall inside
-- its window; later versions (from a real change) open at change time.
INSERT INTO marts.dim_patient
    (patient_id, first_name, last_name, birth_date, gender, city, state, valid_from, valid_to, is_current)
SELECT s.patient_id, s.first_name, s.last_name, s.birth_date, s.gender, s.city, s.state,
       CASE WHEN EXISTS (SELECT 1 FROM marts.dim_patient d2 WHERE d2.patient_id = s.patient_id)
            THEN CURRENT_TIMESTAMP()
            ELSE '1900-01-01'::timestamp_ntz END,
       NULL, TRUE
FROM staging.patients s
LEFT JOIN marts.dim_patient d ON d.patient_id = s.patient_id AND d.is_current = TRUE
WHERE d.patient_id IS NULL;

-- ---------- MARTS: fact ----------
-- SCD2-aware patient join: pick the version valid at the encounter's start time.
INSERT OVERWRITE INTO marts.fact_encounter
    (encounter_id, date_key, patient_sk, provider_sk, facility_sk,
     encounter_class, duration_minutes, observation_count, condition_count)
SELECT
  e.encounter_id,
  TO_NUMBER(TO_CHAR(e.started_at::date, 'YYYYMMDD')),
  p.patient_sk, pr.provider_sk, f.facility_sk,
  e.encounter_class, e.duration_minutes, e.observation_count, e.condition_count
FROM staging.encounters e
LEFT JOIN marts.dim_patient p
       ON p.patient_id = e.patient_id
      AND e.started_at >= p.valid_from
      AND (e.started_at < p.valid_to OR p.valid_to IS NULL)
LEFT JOIN marts.dim_provider pr ON pr.provider_name = e.provider_name
LEFT JOIN marts.dim_facility  f ON f.facility_id    = e.facility_id;
