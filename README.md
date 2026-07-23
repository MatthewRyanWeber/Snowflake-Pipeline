# Snowflake Pipeline

A governance-aware, portfolio-grade **Snowflake data pipeline**. It **moves data** from
source systems (SQL Server, Oracle, files, S3) into Snowflake — ingesting, masking PII, and
loading it incrementally into a governed **RAW → STAGING → MARTS** dimensional model that
downstream BI tools can query.

**The app moves and structures data — it does not compute analytics.** Aggregation and
reporting are left to the BI/query layer on top of the model.

**Standalone / CLI only — no web interface.** Everything runs from Python command-line
modules; orchestration is Snowflake-native (Snowpipe → Streams → Tasks), with GitHub Actions
for deploy + validation.

> Data is fully synthetic — no real records. PII masking and governance controls are built
> and demonstrated as if it were production data.

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
