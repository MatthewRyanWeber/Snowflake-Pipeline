# Snowflake Pipeline

A governance-aware, portfolio-grade **fully-in-Snowflake data pipeline**. It **moves data**
from source systems (SQL Server, Oracle, files, S3) into Snowflake, then does **everything
else natively inside Snowflake**: transform, orchestration, data governance, and audit. The
only external component is the connector that extracts rows from a source database (Snowflake
cannot reach an on-prem/local DB directly — true of any Snowflake pipeline).

- **Transform in Snowflake:** stored procedures on a Streams + Tasks DAG, plus declarative
  **Dynamic Tables** (Snowflake-maintained, no external orchestration).
- **Governance in Snowflake:** native **Dynamic Data Masking** policies + RBAC. PII is masked
  by policy at query time; only an authorized `PII_READER` role sees it in the clear.
- **Audit in Snowflake:** every transfer is logged to `GOV.LOAD_LOG` (plus native
  `COPY_HISTORY` / `ACCESS_HISTORY`).

**The app moves and structures data — it does not compute analytics.** Aggregation and
reporting are left to the BI/query layer on top of the model.

**Standalone / CLI only — no web interface.** Verified live against a local SQL Server.

> Data is fully synthetic — no real records. Masking and governance controls are enforced by
> Snowflake as if it were production data.

## Demo

[![15-second demo](docs/images/sizzle.gif)](docs/videos/snowflake-pipeline-sizzle.mp4)

*15-second overview — click for the full 1080p video ([`docs/videos/`](docs/videos/snowflake-pipeline-sizzle.mp4)).*

## Native Snowflake objects

The transformation and orchestration run **inside Snowflake** (not just an external
connector). Objects created:

| Object | Where | Purpose |
|---|---|---|
| **Tables** | `RAW` / `STAGING` / `MARTS` | landing → cleansed → star schema (fact + dims) |
| **Views** | `STAGING.v_*` | canonical flatten/dedup; call the masking UDFs |
| **Stored Procedures** | `STAGING.sp_ingest`, `sp_build_marts` | the transform logic |
| **Streams** | `RAW.str_patients`, `str_encounters` | change data capture (incremental) |
| **Tasks** | `t_ingest → t_build_marts` | scheduled, stream-gated DAG |
| **Snowpipe** | `RAW.patients_pipe`, `encounters_pipe` | file auto-ingest (S3 event → SQS) |
| **UDFs** | `STAGING.mask_ssn`, `mask_phone` | in-warehouse PII masking |
| **Masking Policies** | `GOV.mask_ssn`, `mask_phone` | Dynamic Data Masking — role-based governance |
| **Dynamic Tables** | `STAGING.dt_*` | declarative, Snowflake-maintained transform |

## Data governance (native, verified live)

PII is stored in RAW and **masked by Snowflake policy at query time**, not by the app:

```
-- same row, two roles:
role PIPELINE_ROLE / ACCOUNTADMIN  ->  ssn = XXX-XX-2073   (masked)
role PII_READER                    ->  ssn = 718-70-2073   (clear, authorized)
```

Every load is recorded in `GOV.LOAD_LOG` (source, target, rows, user, timestamp). Deploy the
governance layer with `python -m scripts.run_sql --dir sql/40_native`.

## CLI in action

Bulk load (SQL Server → Snowflake) with live progress + ETA:

![Loader progress](docs/images/cli-loader.png)

End-to-end run (deploy → ingest → transform → load):

![End to end](docs/images/cli-pipeline.png)

## Architecture

```
                ┌────────────────────────┐
  S3 bucket ──▶ │ Snowpipe (auto-ingest) │──▶ RAW.*  (VARIANT for JSON)
  (JSON/CSV)    └────────────────────────┘
                                                   │  Streams capture changes
  SQL Server ─▶ Python loader (batch) ─────▶ RAW.* │
                                                   ▼
                                          STAGING.*  (cleansed, typed)
                                                   │  Tasks (scheduled DAG)
                                                   ▼
                                          MARTS.*  (star schema: fact + dims,
                                                    incl. one snowflaked dimension)
                                                   ▼
                                          queried by downstream BI tools
```

## Layout

| Path | Purpose |
|---|---|
| `PLAN.md` | Phased build plan — build one phase at a time. |
| `CONVENTIONS.md` | Working conventions for this repo. |
| `sql/00_setup/` | Idempotent SnowSQL: role, warehouse, database, schemas. |
| `sql/10_ingest/` | Stages, file formats, RAW tables, Snowpipe. |
| `sql/30_transform/` | Streams, Tasks DAG, STAGING → MARTS star schema. |
| `loader/` | Python batch loader for relational sources (SQL Server, Oracle, SQLite, files). |
| `scripts/` | `run_sql.py` (deploy), `run_pipeline.py` (end-to-end), loaders, data-quality, teardown. |
| `config/` | Table lists, mappings, schedules (no secrets). |
| `docs/` | Functional spec, technical design, tuning case study, diagrams. |
| `tests/` | Unit tests, runnable with a single command. |

## Status

Phases 0–5 **built and verified live** on a Snowflake account; Phase 6 (docs) complete. The
only unverified piece is S3 Snowpipe *auto-ingest* (needs an AWS bucket + IAM); its COPY/
VARIANT half is verified via an internal stage. See [`PROGRESS.md`](PROGRESS.md).

## Quick start

Credentials go in `~/.snowflake/connections.toml` (connector) or `~/.snowsql/config`
(SnowSQL) — **never** in the repo.

```bash
pip install -r requirements.txt

# One command — deploy + ingest + transform + validate, end to end:
python -m scripts.run_pipeline --num-patients 300
# Clean uninstall when done:  python -m scripts.teardown --yes
```

Or step by step:

```bash
# Deploy each phase (connector-based; no SnowSQL needed):
python -m scripts.run_sql --dir sql/00_setup                 # role, warehouse, DB, schemas
python -m scripts.run_sql --file sql/10_ingest/01_file_formats.sql
python -m scripts.run_sql --file sql/10_ingest/03_raw_tables.sql

# Generate data + load (masked, incremental):
python -m scripts.generate_synthetic_data --num-patients 300 --out-dir data/synthea
python -m loader --config config/loader.local.yaml
python -m scripts.load_internal_stage --file data/synthea/encounters.json --table ENCOUNTERS_JSON --format json --truncate

# Build the star schema + Task DAG:
python -m scripts.run_sql --dir sql/30_transform

# Validate the load:
python -m scripts.data_quality           # referential-integrity + masking checks
```

`scripts/run_sql.py` is the single deploy tool (connector-based, cross-platform, no SnowSQL
install). Full walkthrough: [`docs/demo-script.md`](docs/demo-script.md).

## Docs

Functional spec · technical design · data model · Snowpipe setup · loader · performance
(storage/pruning) case study — all under [`docs/`](docs/).

## Conventions

- No secrets in code or git history — connection config lives outside the repo.
- Every SQL deploy script is idempotent and re-runnable.
- Destructive Python jobs support `--dry-run`.
- All ingested PII is masked on load.

## Environment

Cross-platform: the deploy tool and loaders run via the Snowflake Python connector on Windows
or Linux. Windows-side steps (S3/SQS setup) are called out where they apply.

## License

MIT — see [LICENSE](LICENSE).
