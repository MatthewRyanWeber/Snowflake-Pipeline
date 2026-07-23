# Functional specification

## Purpose

A governance-aware **financial and operational analytics** pipeline that turns raw account
and encounter records into a queryable star schema — with a revenue-cycle fact (charges,
payments, payer mix, claim status) — for BI, using fully synthetic data with production-grade
masking and RBAC.

## Scope

- **In:** ingestion of two source shapes (relational + semi-structured), masking of PII on
  load, transformation into a dimensional model with financial measures, incremental refresh,
  and analytics access.
- **Out:** real records, end-user UI. Data is fully synthetic; a web interface is explicitly
  out of scope (standalone/CLI only).

## Sources

| Source | Shape | Path | Lands in |
|---|---|---|---|
| Patient records | CSV (relational) | S3 → Snowpipe, or Python loader | `RAW.PATIENTS_CSV` |
| Encounters | JSON (semi-structured) | S3 → Snowpipe (VARIANT) | `RAW.ENCOUNTERS_JSON` |

## Business questions answered

1. How many encounters per **region** and encounter class, and average duration? (star +
   snowflake join)
2. Which **providers** see the most patients / record the most observations?
3. What is a patient's **history** when their details change over time? (SCD2)
4. What are the most common **observations** and their average values? (semi-structured
   flatten)
5. How does encounter volume trend over **time**? (date dimension)
6. **Revenue by payer**: charged vs collected, and the collection rate. (financial)
7. **Revenue by region** and outstanding/denied **claim exposure**. (financial + risk)

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
| Snowpark transform, naive vs optimized | ✅ live (206× less data movement) |
| Documented, reproducible tuning win | ✅ live (7.5× fewer partitions) |
