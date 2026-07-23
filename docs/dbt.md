# Phase 3b — dbt models (optional bolt-on)

The `STAGING → MARTS` layer rebuilt as **dbt** models, into a separate `DBT` schema so it
coexists with the native Streams+Tasks pipeline. This is the JD's marketable extra (tests +
lineage + snapshots); the JD is already satisfied without it.

Project: [`dbt/`](../dbt). Profile template: `dbt/profiles.example.yml` (real creds go in
`~/.dbt/profiles.yml`, never the repo).

## What it builds

| Layer | Models |
|---|---|
| staging (views) | `stg_patients`, `stg_encounters`, `stg_observations` (from `RAW` sources) |
| marts (tables) | `dim_date`, `dim_location`, `dim_facility`, `dim_provider`, `dim_patient`, `fact_encounter` |
| snapshot | `patient_snapshot` — **SCD2 via dbt's `check` strategy** (`DBT_SNAPSHOTS` schema) |

Surrogate keys are `md5()` hashes of natural keys (no `dbt_utils` dependency). `dim_patient`
reads the snapshot's `dbt_valid_from/to`; `fact_encounter` joins the current patient version.

## Tests (all data tests, run by `dbt build`)

- `not_null` + `unique` on every dimension surrogate key and `stg_patients.patient_id`
- `accepted_values` on `dim_location.region`
- `relationships` (referential integrity) on every `fact_encounter` FK →
  `dim_facility` / `dim_provider` / `dim_date` / `dim_patient`, plus
  `dim_facility.location_sk → dim_location`

## Run

```bash
cp dbt/profiles.example.yml ~/.dbt/profiles.yml   # then fill creds
dbt build --project-dir dbt      # snapshot + models + tests
dbt docs generate --project-dir dbt && dbt docs serve --project-dir dbt   # lineage graph
```

## Live result (account the Snowflake account)

```
1 snapshot, 6 table models, 20 data tests, 3 view models
PASS=30 WARN=0 ERROR=0 SKIP=0   (10.5s)
```

`fact_encounter` = 1024 rows; every referential-integrity test green.
