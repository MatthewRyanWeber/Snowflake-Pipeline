# Snowflake Pipeline

A governance-aware, portfolio-grade **Snowflake analytics pipeline** for synthetic
healthcare data. It ingests two sources into a raw layer, transforms them via
Snowflake-native Streams + Tasks into a star schema, and exposes them for BI.

**Standalone / CLI only — no web interface.** Everything runs from SnowSQL scripts and
Python command-line jobs; orchestration is Snowflake-native (Snowpipe → Streams → Tasks),
with GitHub Actions for deploy + validation.

> Data is fully synthetic (Synthea). No real PHI. Masking and governance controls are built
> and demonstrated as if it were real.

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
                                          MARTS.*  (star schema: facts + dims,
                                                    one snowflaked dimension)
                                                   ▼
                                          BI / analytics views
```

## Layout

| Path | Purpose |
|---|---|
| `PLAN.md` | Phased build plan — hand Claude Code one phase at a time. |
| `CLAUDE.md` | Working conventions for this repo. |
| `sql/00_setup/` | Idempotent SnowSQL: role, warehouse, database, schemas. |
| `sql/10_ingest/` | Stages, file formats, RAW tables, Snowpipe. |
| `sql/30_transform/` | Streams, Tasks DAG, STAGING → MARTS star schema. |
| `loader/` | Python batch loader for the relational (SQL Server) source. |
| `snowpark/` | Snowpark DataFrame transform (naive vs. optimized). |
| `scripts/` | `deploy.sh` and other run wrappers. |
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
python scripts/run_pipeline.py --num-patients 300
# Clean uninstall when done:  python scripts/teardown.py --yes
```

Or step by step:

```bash
# Deploy each phase (connector-based; no SnowSQL needed):
python scripts/run_sql.py --dir sql/00_setup                 # role, warehouse, DB, schemas
python scripts/run_sql.py --file sql/10_ingest/01_file_formats.sql
python scripts/run_sql.py --file sql/10_ingest/03_raw_tables.sql

# Generate data + load (masked, incremental):
python scripts/generate_synthetic_data.py --num-patients 300 --out-dir data/synthea
python -m loader --config config/loader.local.yaml
python scripts/load_internal_stage.py --file data/synthea/encounters.json --table ENCOUNTERS_JSON --format json --truncate

# Build the star schema + Task DAG:
python scripts/run_sql.py --dir sql/30_transform

# Senior-signal demos:
python snowpark/cohort_aggregation.py    # naive vs optimized pushdown
python scripts/perf_case_study.py        # micro-partition pruning
```

`scripts/deploy.sh` is the equivalent SnowSQL/WSL2 path. Full walkthrough:
[`docs/demo-script.md`](docs/demo-script.md).

## Docs

Functional spec · technical design · data model · Snowpipe setup · loader · Snowpark
optimization · performance case study — all under [`docs/`](docs/).

## Conventions

- No secrets in code or git history — env vars / SnowSQL config only.
- Every SQL deploy script is idempotent and re-runnable.
- Destructive Python jobs support `--dry-run`.
- All ingested PII/PHI is masked on load.

## Environment

Development targets **WSL2 / Linux** shells; Windows-side steps (S3/SQS setup, SnowSQL config
location) are called out explicitly where they apply.

## License

MIT — see [LICENSE](LICENSE).
