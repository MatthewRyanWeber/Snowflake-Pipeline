-- Phase 3 · MARTS dimensions. DDL only, idempotent.
-- Star schema, EXCEPT the location dimension is deliberately SNOWFLAKED:
--   FACT_ENCOUNTER -> DIM_FACILITY -> DIM_LOCATION   (normalized, not collapsed)
-- so both modeling styles are demonstrable by name. DIM_PATIENT is SCD Type 2.

USE ROLE &{sf_role};
USE SCHEMA &{sf_database}.&{sf_schema_marts};

-- Conformed date dimension.
CREATE TABLE IF NOT EXISTS dim_date (
  date_key    NUMBER PRIMARY KEY,     -- YYYYMMDD
  full_date   DATE,
  year        NUMBER,
  month       NUMBER,
  day         NUMBER,
  month_name  STRING,
  day_of_week NUMBER
);

-- Snowflake level 2: normalized location (city/state -> region).
CREATE TABLE IF NOT EXISTS dim_location (
  location_sk NUMBER IDENTITY PRIMARY KEY,
  city        STRING,
  state       STRING,
  region      STRING,
  CONSTRAINT uq_location UNIQUE (city, state)
);

-- Snowflake level 1: facility references location (NOT collapsed into the fact).
CREATE TABLE IF NOT EXISTS dim_facility (
  facility_sk   NUMBER IDENTITY PRIMARY KEY,
  facility_id   STRING,
  facility_name STRING,
  location_sk   NUMBER REFERENCES dim_location(location_sk),
  CONSTRAINT uq_facility UNIQUE (facility_id)
);

CREATE TABLE IF NOT EXISTS dim_provider (
  provider_sk   NUMBER IDENTITY PRIMARY KEY,
  provider_name STRING,
  CONSTRAINT uq_provider UNIQUE (provider_name)
);

-- SCD Type 2 patient dimension: history preserved via valid_from/valid_to/is_current.
CREATE TABLE IF NOT EXISTS dim_patient (
  patient_sk  NUMBER IDENTITY PRIMARY KEY,
  patient_id  STRING,                 -- natural key (not unique: multiple versions)
  first_name  STRING,
  last_name   STRING,
  birth_date  DATE,
  gender      STRING,
  city        STRING,
  state       STRING,
  valid_from  TIMESTAMP_NTZ,
  valid_to    TIMESTAMP_NTZ,
  is_current  BOOLEAN
);
