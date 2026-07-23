# Phase 5 — Performance tuning case study: micro-partition pruning

A reproducible tuning win on Snowflake's core performance lever — **micro-partition
pruning**. Reproduce with [`scripts/perf_case_study.py`](../scripts/perf_case_study.py).

## Setup

Two copies of the same ~2.05M-row fact table (built from `FACT_ENCOUNTER`, widened with a
~300-byte `pad` column so the data spans many micro-partitions):

- `FACT_BIG_RANDOM` — rows inserted in random order.
- `FACT_BIG_SORTED` — rows physically ordered by `date_key` at load (`CTAS … ORDER BY date_key`).

Same selective query on each (one month out of four years), result cache disabled:

```sql
SELECT COUNT(*), AVG(duration_minutes)
FROM MARTS.FACT_BIG_<variant>
WHERE date_key BETWEEN 20250101 AND 20250131;
```

## Symptom → diagnosis → fix → result

**Symptom.** On `FACT_BIG_RANDOM` the query scans **every** micro-partition despite selecting
~1/48th of the data.

**Diagnosis.** `SYSTEM$CLUSTERING_INFORMATION(..., '(date_key)')` reports
`average_depth = 15.0` — every partition's `date_key` range overlaps every other, so no
partition can be skipped. The Query Profile confirms `partitions_scanned = 15 / 15`.

**Fix.** Co-locate rows by the filter column so each partition covers a narrow `date_key`
range. Here that's done by ordering on write (`CTAS … ORDER BY date_key`); in production the
equivalent is a **clustering key** (`ALTER TABLE … CLUSTER BY (date_key)`) maintained by
Automatic Clustering.

**Result (live, account fjliqhb-of64443, XSMALL warehouse).**

| Table | Rows | Partitions total | Partitions scanned | Avg clustering depth |
|---|---|---|---|---|
| `FACT_BIG_RANDOM` | 2,048,000 | 15 | **15 / 15** | 15.00 |
| `FACT_BIG_SORTED` | 2,048,000 | 16 | **2 / 16** | 1.50 |

**7.5× fewer partitions scanned** for identical output — because 14 of 16 partitions were
pruned before any data was read. Clustering depth dropped 15.0 → 1.5 (1.0 is perfectly
clustered).

## Why this is the right lever

Snowflake has no indexes; query performance is dominated by how many micro-partitions a query
must read. Pruning happens on the min/max metadata Snowflake keeps per partition, *before*
scanning — so aligning physical layout to your common filter predicates (date, tenant,
region) is the highest-leverage tuning move. Bigger warehouses make a scan faster; pruning
makes the scan *smaller*, which is cheaper and scales.

## How to reproduce

```bash
python -m scripts.perf_case_study --rowcount 2000
```

Builds both tables, runs the query, prints `partitions_scanned / total` and clustering depth
from the live Query Profile (`GET_QUERY_OPERATOR_STATS`), then drops the big tables.

## Diagnostic toolkit used

- `SYSTEM$CLUSTERING_INFORMATION` — clustering depth / overlap per key.
- `GET_QUERY_OPERATOR_STATS(LAST_QUERY_ID())` — partitions scanned/total, per operator.
- `ALTER SESSION SET USE_CACHED_RESULT = FALSE` — force real scans when measuring.
- (Production) `QUERY_HISTORY`, `WAREHOUSE_LOAD_HISTORY` for spillage and queue diagnosis.
