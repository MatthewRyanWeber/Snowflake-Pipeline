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
| `loader/pipeline.py` | extract → mask → load orchestration |
| `loader/source_sqlserver.py` | SQL Server extractor (pyodbc, lazy) |
| `loader/source_file.py` | CSV stand-in source (offline) |
| `loader/sink_snowflake.py` | Snowflake writer (connector, lazy) |
| `loader/deps.py` | live-dependency gate |

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

## Status

Package + config + tests written; **15 tests green** and the offline dry-run works today.
Live SQL Server → Snowflake path is unverified until the account exists.
