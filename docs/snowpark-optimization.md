# Phase 4 — Snowpark optimization

Snowpark is Snowflake's Spark-style Python DataFrame API: you write DataFrame code, it
compiles to SQL and runs **in** the warehouse. This phase implements one cohort aggregation
two ways and measures the difference — the honest analog to the JD's "optimizing Spark job
performance" bullet (Snowflake doesn't run Spark; Snowpark is the truthful equivalent).

Code: [`snowpark/cohort_aggregation.py`](../snowpark/cohort_aggregation.py). Question:
per `(region, encounter_class)` — encounter count, distinct patients, avg duration, total
observations. `region` comes through the snowflaked `FACT → DIM_FACILITY → DIM_LOCATION` path.

## The two versions

| | naive | optimized |
|---|---|---|
| Join + aggregate | in **pandas on the client** | in the **warehouse** (Snowpark DataFrame) |
| Data crossing the wire | every fact + dim **row** | only the aggregated **result** |
| Pattern | `table.to_pandas()` then `merge`/`groupby` | `join`/`group_by`/`agg`, `to_pandas()` last |

## Measured (live, account fjliqhb-of64443, 1024-row fact)

```
results identical: True
naive:     1.32s, rows pulled to client = 1030
optimized: 2.18s, rows pulled to client = 5
client data movement reduced 206x
```

## Reading the result honestly

- **Data movement: 206× less.** The optimized version ships 5 result rows instead of 1030
  raw rows. This is the number that matters and the one that scales.
- **Wall-clock: optimized was slower here (2.18s vs 1.32s).** On ~1k rows there's nothing to
  push down — the extra warehouse round-trip dominates and the tiny tables pull fast. Not a
  win to oversell at this size.
- **Why it flips at scale:** the naive approach is O(rows transferred + client memory). At
  millions of fact rows it saturates the network and the client's RAM and eventually fails;
  the pushdown stays flat because only the small grouped result ever leaves Snowflake. The
  right way to prove this is to regenerate a multi-million-row fact and re-run — the naive
  curve climbs steeply, the optimized one barely moves.

## Optimization techniques demonstrated

- **Predicate/aggregation pushdown** — compute where the data lives; don't move rows to move
  logic.
- **Minimize materialization** — `to_pandas()` once, on the final small frame, not on base
  tables.
- **Right-sized warehouse** — `PIPELINE_WH` stays XSMALL; the win is from *less work*, not a
  bigger warehouse.

## Status

Verified live: identical results, 206× less client data movement. The wall-clock crossover
(where optimized also wins on time) needs a larger fact table to demonstrate — noted as the
honest next measurement rather than claimed.
