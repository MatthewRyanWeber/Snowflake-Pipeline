# Demo script (3–5 minutes)

A live walkthrough from a clean deploy. Assumes a Snowflake account and
`~/.snowflake/connections.toml` with a `snowflake_pipeline` connection.

## 0. One-time setup (before the demo)

```bash
pip install -r requirements.txt
python -m scripts.run_sql --dir sql/00_setup          # role, warehouse, DB, schemas
python -m scripts.run_sql --file sql/10_ingest/01_file_formats.sql
python -m scripts.run_sql --file sql/10_ingest/03_raw_tables.sql
python -m scripts.generate_synthetic_data --num-patients 300 --out-dir data/synthea
```

## 1. Governance up front (30s)

"Credentials never touch the repo — they're in `~/.snowflake/connections.toml`. Everything
runs as a least-privilege `PIPELINE_ROLE`, not `ACCOUNTADMIN`." Show `config/pipeline.conf`
(names only) and `.gitignore`.

## 2. Ingest + masking (60s)

```bash
python -m loader --dry-run --config config/loader.local.yaml   # shows masked sample, writes nothing
python -m loader --config config/loader.local.yaml             # loads 300 patients
python -m scripts.load_internal_stage --file data/synthea/encounters.json --table ENCOUNTERS_JSON --format json --truncate
```

"SSN and phone are masked on load — raw PII never lands." Then in a worksheet:

```sql
SELECT patient_id, ssn, phone FROM RAW.PATIENTS_CSV LIMIT 3;   -- XXX-XX-####
SELECT v:provider.name::string, v:observations FROM RAW.ENCOUNTERS_JSON LIMIT 1;  -- VARIANT
```

## 3. Semi-structured → the NoSQL story (30s)

```sql
SELECT obs.value:description::string, ROUND(AVG(obs.value:value::float),1)
FROM RAW.ENCOUNTERS_JSON e, LATERAL FLATTEN(input => e.v:observations) obs
GROUP BY 1 ORDER BY 2 DESC;
```

## 4. Build the star schema + SCD2 (60s)

```bash
python -m scripts.run_sql --dir sql/30_transform    # streams, staging, dims, fact, DAG
```

```sql
-- Star + snowflake: encounters by region (fact -> facility -> location)
SELECT l.region, COUNT(*) FROM MARTS.FACT_ENCOUNTER f
JOIN MARTS.DIM_FACILITY fa ON fa.facility_sk=f.facility_sk
JOIN MARTS.DIM_LOCATION l ON l.location_sk=fa.location_sk GROUP BY 1;

-- SCD2: a patient with history
SELECT patient_id, city, valid_from, valid_to, is_current
FROM MARTS.DIM_PATIENT WHERE patient_id='PAT-000001' ORDER BY patient_sk;
```

## 5. Automated refresh (30s)

"Drop a new record in RAW, trigger the DAG, watch it reach the fact." (In the real run this
propagated in ~18s.)

```sql
EXECUTE TASK STAGING.T_STAGE_PATIENTS;   -- root; dependents cascade
SELECT COUNT(*) FROM MARTS.FACT_ENCOUNTER;   -- grows after the DAG runs
```

## 6. Senior signals (45s)

```bash
python -m snowpark.cohort_aggregation     # naive vs optimized: 206x less client data movement
python -m scripts.perf_case_study         # pruning: 15/15 -> 2/16 partitions scanned
```

"Snowpark pushes the aggregation into the warehouse; the tuning study shows micro-partition
pruning cut partitions scanned 7.5×."

## 7. Close (15s)

Point at `docs/` — functional spec, technical design, data model, snowpipe setup. "Rebuildable
from scratch, governed, and every claim here was verified against a live account."
