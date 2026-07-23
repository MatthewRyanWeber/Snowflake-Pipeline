-- Phase 1 · Semi-structured access examples (the VARIANT / "NoSQL" demonstration).
-- Not part of deploy — reference queries you run by hand after data lands.

USE ROLE &{sf_role};
USE WAREHOUSE &{sf_warehouse};
USE SCHEMA &{sf_database}.&{sf_schema_raw};

-- 1) Dot + path access into VARIANT, with typed casts.
SELECT
  v:encounter_id::string     AS encounter_id,
  v:patient_id::string       AS patient_id,
  v:start::timestamp_ntz     AS started_at,
  v:encounter_class::string  AS encounter_class,
  v:provider.name::string    AS provider_name,
  v:provider.facility_name::string AS facility_name
FROM encounters_json
LIMIT 20;

-- 2) LATERAL FLATTEN over the nested observations array → one row per observation.
SELECT
  e.v:encounter_id::string       AS encounter_id,
  obs.value:code::string         AS obs_code,
  obs.value:description::string  AS obs_description,
  obs.value:value::float         AS obs_value,
  obs.value:units::string        AS obs_units
FROM encounters_json e,
     LATERAL FLATTEN(input => e.v:observations) obs
LIMIT 50;

-- 3) Aggregate across the flattened array.
SELECT
  obs.value:code::string         AS obs_code,
  ANY_VALUE(obs.value:description::string) AS description,
  COUNT(*)                       AS n_observations,
  ROUND(AVG(obs.value:value::float), 2)    AS avg_value
FROM encounters_json e,
     LATERAL FLATTEN(input => e.v:observations) obs
GROUP BY obs_code
ORDER BY n_observations DESC;

-- 4) Flatten conditions too (array may be empty → FLATTEN yields no rows for those).
SELECT
  e.v:patient_id::string        AS patient_id,
  cnd.value:code::string        AS condition_code,
  cnd.value:description::string AS condition_description
FROM encounters_json e,
     LATERAL FLATTEN(input => e.v:conditions) cnd
LIMIT 50;
