-- Phase 3 · One-shot backfill. Seeds STAGING from the canonical views (full snapshot),
-- then rebuilds MARTS via the shared procedure. Idempotent; re-runnable.

USE ROLE &{sf_role};
USE WAREHOUSE &{sf_warehouse};
USE SCHEMA &{sf_database}.&{sf_schema_staging};

INSERT OVERWRITE INTO patients
    (patient_id, first_name, last_name, birth_date, gender, city, state, ssn_masked, phone_masked)
SELECT patient_id, first_name, last_name, birth_date, gender, city, state, ssn_masked, phone_masked
FROM v_patients_dedup;

INSERT OVERWRITE INTO encounters
SELECT encounter_id, patient_id, started_at, stopped_at, encounter_class, provider_name,
       facility_id, facility_name, city, state, duration_minutes, observation_count, condition_count
FROM v_encounters_flat;

INSERT OVERWRITE INTO observations
SELECT encounter_id, obs_code, obs_description, obs_value, obs_units
FROM v_observations_flat;

CALL sp_build_marts();
