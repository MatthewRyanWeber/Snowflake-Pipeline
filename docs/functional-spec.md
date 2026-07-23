# Functional specification

## Purpose

A governance-aware **data pipeline** that moves records from source systems into a governed
Snowflake dimensional model (RAW → STAGING → MARTS), masking PII on load, using fully
synthetic data with production-grade RBAC. The app **moves and structures data** — it does
not compute analytics; querying/aggregation is left to BI tools on top of the model.

## Scope

- **In:** ingestion of two source shapes (relational + semi-structured), masking of PII on
  load, transformation into a dimensional model (dedup, typing, conforming, SCD2), incremental
  refresh, and data-integrity validation.
- **Out:** analytics/reporting computed by the app, real records, end-user UI. Data is fully
  synthetic; a web interface is explicitly out of scope (standalone/CLI only).

## Sources

| Source | Shape | Path | Lands in |
|---|---|---|---|
| Patient records | CSV (relational) | S3 → Snowpipe, or Python loader | `RAW.PATIENTS_CSV` |
| Encounters | JSON (semi-structured) | S3 → Snowpipe (VARIANT) | `RAW.ENCOUNTERS_JSON` |

## Queries the model supports (run by BI tools, not the app)

The landed dimensional model is shaped so downstream tools can query:

1. Encounters by **region** and class (star + snowflake join).
2. **Provider** and **payer** rollups (conformed dimensions).
3. A patient's **history** as details change over time (SCD2).
4. Observations flattened from the semi-structured source.
5. Trends over **time** (date dimension).

The pipeline builds and loads these structures; it does not run the queries itself.

## Data governance requirements

- All PII (SSN, phone) **masked on load**; raw values never persist in `RAW`.
- **RBAC**: a single least-privilege role (`PIPELINE_ROLE`) owns all objects; no work done as
  `ACCOUNTADMIN`.
- **No secrets** in code or git; credentials in the SnowSQL/connector config only.
- Destructive loads support **`--dry-run`**.
- Loads are **incremental and idempotent** (high-water-mark; re-runs never duplicate).

## Non-functional requirements

- Rebuildable from scratch with one command per phase (idempotent SQL).
- Trial-credit safe: XSMALL warehouse, 60s auto-suspend, tasks suspended when idle.
- Runs on Windows (Python connector) and WSL2/Linux (SnowSQL) alike.

## Acceptance (all verified live except S3 auto-ingest)

| Requirement | Status |
|---|---|
| Env rebuilds from scratch, zero clicks | ✅ live |
| Files/relational rows land in RAW; JSON queryable as VARIANT | ✅ live (auto-ingest via S3 needs AWS) |
| PII masked on load; incremental, no duplicates | ✅ live (300 rows, re-run = 0) |
| Star + snowflake schema; SCD2 history | ✅ live |
| Automated refresh (Streams + Tasks) | ✅ live (new row → fact in 18s) |
| Incremental load throughput (bulk COPY) | ✅ live (~2,600 rows/s, 100k rows) |
| Documented, reproducible storage-tuning win | ✅ live (7.5× fewer partitions) |
