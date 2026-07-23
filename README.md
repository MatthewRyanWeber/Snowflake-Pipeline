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

## Quick start

Not yet deployable — this is the Phase 0 skeleton. See `PLAN.md`.

1. Sign up for the Snowflake 30-day trial; note the account identifier.
2. Install SnowSQL; configure a named connection (`~/.snowsql/config` — **never** hardcode
   creds).
3. `./scripts/deploy.sh` rebuilds the full role/warehouse/schema layout from scratch.

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
