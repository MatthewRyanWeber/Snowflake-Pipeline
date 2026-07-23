-- Phase 6 · BI / analytics serving views over MARTS. Idempotent (CREATE OR REPLACE VIEW).
-- One view per functional-spec business question. These are what a BI tool points at.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_marts};

-- Q1: encounters by region + class (star + snowflake join).
CREATE OR REPLACE VIEW vw_encounters_by_region AS
SELECT l.region, f.encounter_class,
       COUNT(*)                              AS encounters,
       COUNT(DISTINCT f.patient_sk)          AS patients,
       ROUND(AVG(f.duration_minutes), 1)     AS avg_duration_min,
       SUM(f.observation_count)              AS total_observations
FROM fact_encounter f
JOIN dim_facility fa ON fa.facility_sk = f.facility_sk
JOIN dim_location l  ON l.location_sk  = fa.location_sk
GROUP BY l.region, f.encounter_class;

-- Q2: provider productivity.
CREATE OR REPLACE VIEW vw_provider_productivity AS
SELECT p.provider_name,
       COUNT(*)                       AS encounters,
       COUNT(DISTINCT f.patient_sk)   AS distinct_patients,
       SUM(f.observation_count)       AS total_observations,
       ROUND(AVG(f.duration_minutes), 1) AS avg_duration_min
FROM fact_encounter f
JOIN dim_provider p ON p.provider_sk = f.provider_sk
GROUP BY p.provider_name;

-- Q3: current-version patient roster (SCD2 -> current slice).
CREATE OR REPLACE VIEW vw_patient_current AS
SELECT patient_id, first_name, last_name, birth_date, gender, city, state, valid_from
FROM dim_patient
WHERE is_current;

-- Q4: observation summary (semi-structured flatten, served relationally).
CREATE OR REPLACE VIEW vw_observation_summary AS
SELECT obs_code, ANY_VALUE(obs_description) AS description,
       COUNT(*) AS n_observations,
       ROUND(AVG(obs_value), 2) AS avg_value
FROM &{sf_database}.&{sf_schema_staging}.observations
GROUP BY obs_code;

-- Q5: monthly encounter trend (date dimension).
CREATE OR REPLACE VIEW vw_monthly_encounter_trend AS
SELECT d.year, d.month, d.month_name,
       COUNT(*) AS encounters,
       COUNT(DISTINCT f.patient_sk) AS patients
FROM fact_encounter f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month, d.month_name;
