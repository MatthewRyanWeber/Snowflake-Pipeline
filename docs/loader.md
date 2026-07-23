# Phase 2 — Relational source loader (Python)

Extracts from SQL Server and loads into Snowflake `RAW`, incrementally and idempotently,
masking PII on the way in. Governance ported from the framework standards: structured
logging, `argparse` CLI, file locking, `--dry-run`, config-driven, no secrets in code.

## Design

```
SQL Server ──(fetch_batches, WHERE hwm > last ORDER BY hwm)──▶ mask_row (PII) ──▶ Snowflake RAW
                                                                     │
                                          checkpoint after each committed batch ──▶ state/watermarks.json
```

- **Incremental / resumable:** each table has a high-water-mark column. Only rows past the
  stored watermark are read; the watermark advances only *after* a batch commits, so a crash
  resumes without re-loading or skipping.
- **Masking on load:** `loader/masking.py` (pure, unit-tested) applies per-column policies
  (`ssn`, `phone`, `email`, `redact`, `hash`) named in `config/loader.yaml`.
- **Pluggable source:** `source.type: sqlserver` for real loads, `source.type: file` to run
  end-to-end offline against a CSV (used for dry-run + tests before a DB exists).
- **Safety:** `loader/lock.py` (atomic lock file) stops two runs colliding on shared state;
  `loader/deps.py` aborts loud if a live driver is missing (never silently skips).

## Layout

| File | Role |
|---|---|
| `loader/__main__.py` | CLI (`python -m loader`) |
| `loader/config.py` | load + validate `config/loader.yaml` |
| `loader/masking.py` | PII masking policies (pure) |
| `loader/watermark.py` | persisted high-water-mark checkpoints |
| `loader/lock.py` | portable advisory file lock |
| `loader/pipeline.py` | extract → mask → load orchestration + progress/ETA |
| `loader/source_sqlserver.py` | SQL Server extractor (pyodbc, lazy) |
| `loader/source_oracle.py` | Oracle extractor (oracledb thin, lazy) |
| `loader/source_sqlite.py` | SQLite extractor (stdlib) |
| `loader/source_file.py` | CSV stand-in source (offline) |
| `loader/sink_snowflake.py` | Snowflake writer — `write_pandas` bulk COPY, `INSERT` fallback |
| `loader/progress.py` | progress bar + throughput + ETA |
| `loader/retry.py` | retry-with-backoff for transient connects |
| `loader/deps.py` | live-dependency gate |

## Sources (swap by config, not code)

`source.type` selects the extractor: `sqlserver`, `oracle`, `sqlite`, or `file`. All honor the
same `fetch_batches` + `count` contract, so adding a database means a ~40-line source class,
not a pipeline change. Oracle/SQL Server passwords come from env or trusted auth, never config.

## Progress & throughput

The loader counts the pending rows up front and prints a live bar with rows/s and ETA:

```
patients->PATIENTS_CSV [#############-----------]  56.0% (11200/20000) 2238 rows/s ETA 4s
```

Writes use Snowflake's `write_pandas` (parquet + COPY) — ~2,200 rows/s on a wide table vs
~300 rows/s for row-by-row `INSERT` (the fallback when pandas is absent). Verified live:
20,000 SQL Server rows in ~9s.

## Secrets

None in the repo. Snowflake auth = the named connection in `~/.snowsql/config`. SQL Server
auth = an ODBC DSN or trusted/Windows auth (or an env-referenced connection string). Never
inline a password in `config/loader.yaml`.

## Run

```bash
# Offline, no database — proves the flow and shows masked output:
python -m loader --dry-run --config config/loader.sample.yaml

# Live dry-run against SQL Server (reads, writes nothing):
python -m loader --dry-run

# Real incremental load:
python -m loader                      # all tables
python -m loader --table patients     # one table
```

Install live drivers first: `pip install -r requirements.txt`.

## Acceptance

- `python -m loader --dry-run` reports intended row counts + a masked sample, writes nothing,
  leaves the watermark untouched. **(Verified offline against the synthetic sample.)**
- A real run is incremental and re-runnable without duplicates; masked columns land masked.
  **(Pending a live SQL Server + Snowflake account.)**

## Tests

`python -m pytest tests/ -q` — masking, watermark persistence + corruption-fails-loud,
dry-run-writes-nothing, incremental-resume-from-watermark, file source ordering.

## Known limitations & design notes (by design, not bugs)

- **RAW is an at-least-once landing zone.** The watermark advances only after a batch commits,
  so a crash *between* the commit and the watermark flush can re-append that batch's rows to
  RAW on the next run. This is intentional landing-zone behavior: STAGING dedupes by natural
  key (`ROW_NUMBER() … latest`), so duplicates never reach the marts. Exactly-once into RAW
  would require a keyed MERGE, which fights the append-only landing design.
- **`hwm_column` must be monotonic.** Incremental correctness relies on the source returning
  rows `ORDER BY hwm ASC`; the loader takes the last row's value as the checkpoint (native
  type, no client-side comparison). A non-increasing key can skip rows.
- **File source loads the whole CSV into memory** (to sort it) — fine for the dev/offline
  path; the SQL sources stream in batches server-side.
- **Bulk-load scale.** The sink uses parameterized multi-row `INSERT` (the connector batches
  `INSERT … VALUES` into one request). For very large loads, stage-and-`COPY` (à la
  `scripts/load_internal_stage.py`) is faster; the loader targets correctness + masking on a
  moderate relational feed.
- **`TrustServerCertificate=yes`** in the SQL Server config skips TLS cert validation — fine
  for a local instance, but use a trusted cert in production.

## Status

Verified live against account the Snowflake account via file, SQLite, **and a real local SQL Server
2025** — 300 rows masked, incremental re-run = 0. **19 unit tests green** (incl. native-type
watermark, injection-guard, non-string masking).
