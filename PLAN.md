# Snowflake Pipeline — Build Plan for Claude Code

**Purpose:** A portfolio-grade, governance-aware Snowflake analytics pipeline whose
features map 1:1 onto the *Sr Snowflake Data Engineer* JD (NYC). Built so you can demo a
real, running solution and speak to every bullet in an interview.

**How to use this doc:** Drop it into the repo root (e.g. `PLAN.md`) and hand phases to
Claude Code one at a time. Each phase has a goal, tasks, deliverables, and acceptance
criteria. Don't run them all at once — build → verify → commit per phase.

---

## JD → project coverage (the scoreboard)

| JD requirement | Where it's covered |
|---|---|
| SnowSQL, Snowpipe | Phase 0 (SnowSQL deploy scripts), Phase 1 (Snowpipe auto-ingest) |
| Big-data modeling with Python | Phase 2 (Python loader), Phase 4 (Snowpark) |
| Snowflake internals + performance tuning + troubleshooting | Phase 5 (tuning case study) |
| Relational **and** NoSQL/semi-structured stores | Phase 1 (JSON → VARIANT), Phase 2 (SQL Server source) |
| Star **and** snowflake dimensional modeling | Phase 3 (star schema + one deliberately snowflaked dim) |
| Automating pipelines, cloud-based | Phase 1 (auto-ingest), Phase 3 (Streams + Tasks DAG), Phase 6 (CI) |
| Document requirements / technical + functional specs | Phase 6 (functional spec + technical design doc) |
| Demonstrate solution, communication | Phase 6 (README walkthrough, architecture diagram, demo script) |
| "Optimizing Spark job performance" | Phase 4 (Snowpark — the honest analog; see note) |

---

## Project concept

A **synthetic healthcare analytics pipeline** — reuses your existing PHI/HIPAA governance
work and your familiarity with health-shaped sample data. Ingests two sources into a raw
layer, transforms via Snowflake-native Streams + Tasks into a star schema, and exposes it
for BI. Use fully synthetic data (e.g. Synthea) — no real PHI, but the masking/governance
controls are built and demonstrated as if it were real.

### Tech decisions (my three questions, answered from the JD)

- **Source:** *Both.* Files landed in cloud storage (S3) for Snowpipe, **plus** a batch
  pull from a relational DB (SQL Server) via Python. This literally satisfies both the
  Snowpipe bullet and the "relational + NoSQL" bullet.
- **Transformations:** *Snowflake-native core* (Streams + Tasks + SnowSQL) because the JD
  names those explicitly and never mentions dbt. dbt is added as an **optional Phase 3b**
  bolt-on for tests/lineage polish if you want the marketable extra — but the JD is proven
  without it.
- **Orchestration:** *Snowflake-native* (Snowpipe auto-ingest → Streams → Tasks DAG), with
  GitHub Actions running deploy + validation. No Airflow needed to satisfy this JD.

### Architecture

```
                ┌────────────────────────┐
  S3 bucket ──▶ │ Snowpipe (auto-ingest)  │──▶ RAW.*  (VARIANT for JSON)
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

---

## Phase 0 — Foundation

**Goal:** Snowflake account, deployable-from-scratch environment, repo skeleton.

**Tasks**
- Sign up for the Snowflake 30-day free trial; note account identifier.
- Install SnowSQL CLI; configure a named connection (never hardcode creds — use
  `~/.snowsql/config` or env vars).
- Create RBAC: a dedicated role, warehouse (start `XSMALL`, auto-suspend 60s), database,
  and schemas `RAW`, `STAGING`, `MARTS`.
- Write everything as **idempotent SnowSQL scripts** under `sql/00_setup/` so the whole env
  rebuilds with one command.
- Init GitHub repo (handle: MatthewRyanWeber), `.gitignore` for creds/keys, MIT license,
  README stub.

**Deliverables:** `sql/00_setup/*.sql`, `scripts/deploy.sh` (runs setup via SnowSQL), repo.

**Acceptance:** `./scripts/deploy.sh` on a clean account produces the full role/warehouse/
schema layout with zero manual clicks.

---

## Phase 1 — Snowpipe ingestion (files → RAW, incl. semi-structured)

**Goal:** Auto-ingesting file pipeline + the "NoSQL"/VARIANT story.

**Tasks**
- Generate synthetic data (Synthea) as **both** CSV and JSON.
- Create an external stage on S3, a file format per type, and target RAW tables.
- Land JSON into a `VARIANT` column; write query examples using dot/lateral-flatten access
  (this is the semi-structured / NoSQL demonstration).
- Configure **Snowpipe with auto-ingest** (S3 event notification → SQS). Document the setup
  end to end.
- Add a manual `COPY INTO` fallback path for troubleshooting demos.

**Deliverables:** `sql/10_ingest/`, a `docs/snowpipe-setup.md`, sample files, flatten queries.

**Acceptance:** Dropping a new file in S3 lands rows in RAW within a minute, no manual step;
JSON is queryable via VARIANT.

---

## Phase 2 — Relational source loader (Python)

**Goal:** Cover "Python + a major relational database" and reuse your framework's governance.

**Tasks**
- Python job that extracts from SQL Server (or Postgres) and loads to `RAW` via the
  Snowflake Python connector (or Snowpark write).
- Port your framework's governance standards: versioning, structured logging, `--dry-run`,
  PII masking on load, `argparse` CLI, file locking.
- Idempotent/incremental load via a high-water-mark column.
- Config-driven (table list, mappings) — no secrets in code.

**Deliverables:** `loader/` package, `config/loader.yaml`, unit tests, `docs/loader.md`.

**Acceptance:** `python -m loader --dry-run` reports intended changes; a real run is
incremental and re-runnable without duplicates; masked columns land masked.

---

## Phase 3 — Streams + Tasks → star schema

**Goal:** The native automation DAG + the dimensional modeling centerpiece.

**Tasks**
- Create **Streams** on RAW tables to capture change.
- Build `STAGING` transforms (typing, dedup, conformance) consuming the streams.
- Model `MARTS` as a **star schema**: fact table(s) + conformed dimensions.
- Include **one deliberately snowflaked dimension** (e.g. normalized location →
  facility → region) so you can speak to *both* modeling styles by name.
- Wire a **Task DAG** (root task + dependent tasks) on a schedule to run staging → marts.
- SCD Type 2 on at least one dimension for depth.

**Deliverables:** `sql/30_transform/`, ER/diagram in `docs/data-model.md`.

**Acceptance:** New raw rows flow automatically through streams → staging → marts on the
Task schedule; star and snowflake structures both queryable; SCD2 history verifiable.

**Optional Phase 3b (dbt):** Rebuild the STAGING→MARTS layer as dbt models with tests +
docs/lineage. Purely additive marketability; skip if time-boxed.

---

## Phase 4 — Snowpark transformation (the "Spark" bullet, honestly)

**Goal:** Demonstrate the DataFrame/Spark-style skill the JD gestures at, done the Snowflake
way.

> **Note:** Snowflake doesn't run Spark. Snowpark is its Spark-like Python DataFrame API that
> pushes computation down into the warehouse. Building a Snowpark transform lets you speak to
> "Spark-style job optimization" truthfully rather than claiming Spark experience you don't
> have.

**Tasks**
- Implement one non-trivial transform (e.g. patient-cohort aggregation) as a Snowpark Python
  job.
- Write it two ways — naive vs. optimized (predicate pushdown, minimizing collect/materialize,
  right-sized warehouse) — and document the difference.

**Deliverables:** `snowpark/`, `docs/snowpark-optimization.md` with before/after.

**Acceptance:** Both versions produce identical output; the optimized one shows measurably
less compute in the query history.

---

## Phase 5 — Performance tuning case study

**Goal:** Directly satisfy "performance tuning of the snow pipelines and troubleshoot
quickly" — this is the phase interviewers probe hardest.

**Tasks**
- Take one deliberately slow query/table and tune it: clustering key selection,
  micro-partition pruning, warehouse sizing, result caching, avoiding spillage.
- Use **Query Profile** and `QUERY_HISTORY` / `WAREHOUSE_LOAD_HISTORY` to diagnose.
- Write it up as a narrative: symptom → diagnosis → fix → measured result.

**Deliverables:** `docs/performance-case-study.md` with query profiles and before/after
timings + credit usage.

**Acceptance:** A documented, reproducible tuning win you can walk through verbally in 3–4
minutes.

---

## Phase 6 — Docs, spec, and demo

**Goal:** Cover "document requirements, technical + functional specs" and "demonstrate the
solution with communication skill" — both are literal JD bullets.

**Tasks**
- `docs/functional-spec.md` — requirements, sources, business questions answered.
- `docs/technical-design.md` — architecture, data flow, RBAC, decisions + tradeoffs.
- Architecture diagram (the ASCII above, upgraded to a real diagram).
- README: what it is, how to deploy from scratch, how to demo.
- A 3–5 minute demo script (or Loom) walking the pipeline end to end.

**Acceptance:** A stranger can clone the repo, read the specs, and understand the whole
solution in 10 minutes; you can demo it live from a clean deploy.

---

## Governance conventions (apply throughout)

- Versioning, structured logging, `--dry-run` where destructive, PII masking, `argparse`,
  file locking — your existing framework standards.
- No secrets in code or git history; env vars / SnowSQL config only.
- Every SQL deploy script idempotent and re-runnable.
- Flag any assumption in a `# ASSUMPTION:` comment rather than presenting it as settled.

## Sequencing notes

- Phases 0→1→2 build the ingestion floor; 3 is the modeling centerpiece; 4–5 are the
  senior-signal phases (Snowpark + tuning) that separate you from a junior; 6 makes it
  legible to interviewers.
- If time-boxed, a credible minimum is **0, 1, 3, 5, 6**. Add 2 and 4 to fully cover the JD.
- Watch trial credits — keep the warehouse `XSMALL` with aggressive auto-suspend.
