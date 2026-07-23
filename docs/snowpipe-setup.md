# Phase 1 — Snowpipe ingestion setup

Auto-ingesting pipeline: files land in S3 → Snowpipe (S3 event → SQS) loads them into
`RAW` within ~a minute, no manual step. Plus a manual `COPY INTO` fallback and the
VARIANT/JSON "semi-structured" demonstration.

## What gets built

| Object | Name | File |
|---|---|---|
| Storage integration | `HEALTH_S3_INT` | `sql/10_ingest/00_storage_integration.sql` |
| File formats | `csv_format`, `json_format` | `01_file_formats.sql` |
| External stage | `RAW.HEALTH_STAGE` | `02_stage.sql` |
| RAW tables | `RAW.PATIENTS_CSV`, `RAW.ENCOUNTERS_JSON` | `03_raw_tables.sql` |
| Pipes (auto-ingest) | `RAW.PATIENTS_PIPE`, `RAW.ENCOUNTERS_PIPE` | `04_snowpipe.sql` |
| Manual fallback / flatten | — | `sql/10_ingest/manual/` |

## Data

Generate Synthea-shaped files (stdlib Python, no deps):

```bash
python scripts/generate_synthetic_data.py --num-patients 200 --seed 42 --out-dir data/synthea
# -> data/synthea/patients.csv   (structured → PATIENTS_CSV)
# -> data/synthea/encounters.json (NDJSON, nested arrays → ENCOUNTERS_JSON VARIANT)
```

> **ASSUMPTION / honesty:** this generator is a dependency-free stand-in so the pipeline is
> buildable and testable offline. The plan names **Synthea** (a Java tool). Real Synthea
> output can replace these files unchanged — RAW only depends on the CSV columns and the JSON
> shape, not the producer. Swap in real Synthea before calling this "Synthea data" in the demo.

Upload to S3 (Windows-side or WSL2, wherever the AWS CLI is configured):

```bash
aws s3 cp data/synthea/patients.csv    s3://<bucket>/health/
aws s3 cp data/synthea/encounters.json s3://<bucket>/health/
```

## AWS setup (one time) — the part that must be done outside Snowflake

**These are Windows/AWS-side steps; the SQL can't do them for you.** Order matters because
Snowflake generates the trust principals *after* the integration exists.

1. **S3 bucket** — create it; note the URL `s3://<bucket>/health/`.
2. **IAM policy** — allow `s3:GetObject`, `s3:GetObjectVersion` on `.../health/*` and
   `s3:ListBucket` on the bucket.
3. **IAM role** — attach the policy. Trust policy is a placeholder for now (you fill the real
   principal in step 6). Put the role ARN in `SF_STORAGE_AWS_ROLE_ARN` and the bucket URL in
   `SF_S3_URL` in `config/pipeline.conf`.
4. **Create the integration + stage:**
   ```bash
   python scripts/run_sql.py --dir sql/10_ingest --dry-run   # preview
   python scripts/run_sql.py --dir sql/10_ingest             # create objects
   ```
5. **`DESC INTEGRATION HEALTH_S3_INT;`** (printed by `00_storage_integration.sql`) — copy
   `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`.
6. **Finish the IAM role trust policy** — set `Principal.AWS` to the IAM user ARN and add a
   `sts:ExternalId` condition with the external ID from step 5. Now the stage can read S3;
   verify with `LIST @RAW.HEALTH_STAGE;`.
7. **Wire auto-ingest** — `SHOW PIPES IN SCHEMA RAW;` and copy each pipe's
   `notification_channel` (an SQS ARN). In the S3 bucket → Properties → Event notifications,
   add an **All object create** event with destination **SQS queue** = that ARN. (Both pipes
   share the bucket's one notification; a single event fanning to the same SQS is fine.)

## Verify (acceptance)

```sql
-- Drop a fresh file in S3, wait ~60s, then:
SELECT COUNT(*) FROM RAW.PATIENTS_CSV;
SELECT COUNT(*) FROM RAW.ENCOUNTERS_JSON;

-- Pipe health / errors:
SELECT SYSTEM$PIPE_STATUS('RAW.PATIENTS_PIPE');
SELECT * FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
  TABLE_NAME => 'RAW.ENCOUNTERS_JSON', START_TIME => DATEADD('hour', -1, CURRENT_TIMESTAMP())));

-- Semi-structured access (see sql/10_ingest/manual/flatten_queries.sql for more):
SELECT v:encounter_id::string, v:provider.name::string FROM RAW.ENCOUNTERS_JSON LIMIT 10;
```

**Acceptance:** a new file dropped in S3 lands rows in RAW within a minute with no manual
step, and the JSON is queryable via VARIANT + `LATERAL FLATTEN`.

## Troubleshooting

- **Nothing loads** → check `SYSTEM$PIPE_STATUS`; confirm the S3 event actually targets the
  pipe's SQS ARN; confirm `LIST @RAW.HEALTH_STAGE` shows the files (integration/trust issue if
  empty).
- **Files load but rows are wrong** → run `sql/10_ingest/manual/copy_manual.sql`, or a
  `COPY ... VALIDATION_MODE='RETURN_ERRORS'` to see per-row parse errors synchronously.
- **Re-loading the same file** → Snowpipe dedupes by filename for ~14 days; rename the file to
  force a reload during testing.
