# Phase 3 — Data model (STAGING → MARTS)

The `MARTS` layer is a **star schema** with one deliberately **snowflaked** dimension, built
and kept current by **Streams + a Task DAG**. `DIM_PATIENT` is **SCD Type 2**.

## Star + snowflake

```
                         DIM_DATE
                            │
        DIM_PROVIDER ── FACT_ENCOUNTER ── DIM_PATIENT  (SCD2)
                            │
                       DIM_FACILITY ─────► DIM_LOCATION   ◄── snowflaked arm
                       (facility_sk)        (location_sk → region)
```

- **Star:** `FACT_ENCOUNTER` joins directly to `DIM_DATE`, `DIM_PROVIDER`, `DIM_PATIENT`, and
  `DIM_FACILITY` on surrogate keys.
- **Snowflake:** `DIM_FACILITY` does **not** carry city/state/region columns; it references
  `DIM_LOCATION` (normalized second level: `city, state → region`). So a "encounters by
  region" query traverses `FACT → DIM_FACILITY → DIM_LOCATION` — the textbook snowflake shape,
  kept alongside the otherwise-star model on purpose.

## Grain & measures

`FACT_ENCOUNTER` — one row per encounter. Measures: `duration_minutes`, `observation_count`,
`condition_count`. `encounter_id` is a degenerate dimension (natural key kept on the fact).

## Dimensions

| Dimension | Key | Notes |
|---|---|---|
| `DIM_DATE` | `date_key` (YYYYMMDD) | conformed calendar, generated 2023–2026 |
| `DIM_PATIENT` | `patient_sk` (identity) | **SCD2**: `valid_from`/`valid_to`/`is_current` |
| `DIM_PROVIDER` | `provider_sk` | conformed |
| `DIM_FACILITY` | `facility_sk` | → `DIM_LOCATION` (snowflake) |
| `DIM_LOCATION` | `location_sk` | `city, state, region` |

## SCD Type 2 (patient)

Two-step, idempotent:
1. **Expire** — for each `is_current` patient whose tracked attributes (name, gender, birth
   date, city, state) changed vs. STAGING, set `valid_to = now`, `is_current = false`.
2. **Insert** — add a fresh current version for brand-new patients and just-expired ones. The
   *first* version opens at `1900-01-01` so historical encounters fall inside its window;
   later versions open at change time.

The fact's patient join is SCD2-aware: it picks the version whose `[valid_from, valid_to)`
window contains the encounter's start — so a re-addressed patient's old encounters stay tied
to their old location, new ones to the new location. **Verified live:** relocating a patient
produced a second version; historical encounters still resolved to the prior version.

## Incremental engine: Streams + Task DAG

The transform logic has exactly one home. Flatten/dedup rules live in staging **views**
(`v_patients_dedup`, `v_encounters_flat`, `v_observations_flat`, in `01_staging.sql`), and
region / SCD2 / the fact join live in two **stored procedures** (`sp_ingest`,
`sp_build_marts`, in `04_procedures.sql`). Both the backfill and the DAG call the same
procedures, so nothing is duplicated.

- **Streams** `RAW.STR_PATIENTS`, `RAW.STR_ENCOUNTERS` (APPEND_ONLY) capture new RAW rows.
- **Backfill** (`05_backfill.sql`) seeds STAGING from the views, then `CALL sp_build_marts()`.
- **Task DAG** (`06_tasks.sql`) keeps it current: two tasks on `PIPELINE_WH`, gated by
  `SYSTEM$STREAM_HAS_DATA`, `SCHEDULE = 1 MINUTE`:

```
t_ingest (root, stream-gated)  ->  CALL sp_ingest()       -- consume streams into STAGING
   └─ t_build_marts            ->  CALL sp_build_marts()   -- rebuild dims, SCD2, fact
```

`sp_ingest` consumes each stream once (into a temp table) and applies the canonical views to
the new keys; consuming the streams advances their offsets, which resets the WHEN gate.
**Verified live:** a new record propagates root → dependent → `FACT_ENCOUNTER` in ~18s.

## Live-verified counts (account fjliqhb-of64443, 300 patients / 1023 encounters)

`FACT_ENCOUNTER` 1023 · `DIM_PATIENT` 300 current · `DIM_PROVIDER` 5 · `DIM_FACILITY` 3 ·
`DIM_LOCATION` 3 (all Northeast region) · `DIM_DATE` 1461. Zero unmatched dimension keys on
the fact.
