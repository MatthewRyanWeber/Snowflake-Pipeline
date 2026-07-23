# Benchmarks — full-volume timed run

End-to-end run using **everything in the SQL database** (all patients), on the live account
`the Snowflake account` (XSMALL warehouse), local SQL Server 2025 source, Python connector.

Dataset: **100,000 patients**, **349,821 encounters**, **1,225,569 observations**.

| # | Stage | Rows | Time |
|---|---|---|---|
| 1 | Generate synthetic data | 100k patients + 349,821 encounters | 14.5s |
| 2 | Load into SQL Server (`dbo.patients`) | 100,000 | 3.3s |
| 3 | **Loader: SQL Server → RAW** (masked, `write_pandas` bulk COPY) | 100,000 | **42.3s (2,615 rows/s)** |
| 4 | Encounters → RAW (internal-stage COPY, VARIANT) | 349,821 | 23.7s |
| 5 | Transform backfill: STAGING + MARTS (stored procs) | → 1,225,569 obs | 38.6s |
| 6 | Data-quality gate (12 checks) | — | 6.9s |
|   | **Total** | | **~129s (~2.2 min)** |

Result: **12/12 data-quality checks pass**; `FACT_ENCOUNTER` and `DIM_PATIENT` populated
(counts include ~1,024 encounters / 303 patients from earlier tests, since only RAW was
truncated for this run, not MARTS).

## Loader throughput: the bottleneck fix

The relational load (stage 3) writes via Snowflake's `write_pandas` (parquet + COPY):

| Write path | Throughput | 20k rows | 100k rows |
|---|---|---|---|
| Row-by-row `INSERT` (old) | ~300 rows/s | ~65s | ~5.5 min (extrapolated) |
| `write_pandas` bulk COPY (now) | ~2,600 rows/s | ~9s | **42.3s** |

**~7–9× faster.** `INSERT` remains as the fallback when pandas is unavailable. The live
progress bar reports percent, rows/s, and ETA throughout.
