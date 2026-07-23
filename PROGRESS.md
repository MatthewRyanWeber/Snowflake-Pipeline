# PROGRESS — Snowflake Pipeline

Durable, git-tracked build status. The source of truth for resuming across sessions.
Full detail lives in [`PLAN.md`](PLAN.md); conventions in [`CONVENTIONS.md`](CONVENTIONS.md).

**To resume:** open this file, find the first unchecked box, say "continue with Phase N."

---

## Overall status

| Phase | Title | Status |
|---|---|---|
| 0 | Foundation | ✅ **Deployed + validated LIVE** on account fjliqhb-of64443 |
| 1 | Snowpipe ingestion (files → RAW) | ✅ RAW tables + VARIANT/FLATTEN verified LIVE; ⬜ S3 *auto-ingest* needs AWS |
| 2 | Relational source loader (Python) | ✅ **Verified LIVE**: 300 rows loaded, masked, incremental re-run = 0 dupes |
| 3 | Streams + Tasks → star schema | ✅ **Built + verified LIVE** (star+snowflake, SCD2, 10-task DAG propagates in 18s) |
| 4 | Snowpark transformation | ✅ **Verified LIVE**: naive vs optimized, identical results, 206× less client data movement |
| 5 | Performance tuning case study | ✅ **Verified LIVE**: pruning 15/15 → 2/16 partitions (7.5× fewer) |
| 6 | Docs, spec, demo | ✅ **Complete**: functional spec, technical design (mermaid), demo script, README |

Legend: ✅ done · 🟡 in progress · ⬜ not started

**Time-boxed minimum path:** 0, 1, 3, 5, 6 (add 2 and 4 for full JD coverage).

---

## Phase 0 — Foundation

- [x] GitHub repo created — private, `MatthewRyanWeber/snowflake-pipeline`
- [x] Repo skeleton: directory scaffold, README, MIT LICENSE, `.gitignore`
- [x] 20 repo topics added
- [x] `PLAN.md` in place (renamed from `snowflake-pipeline-plan.md`)
- [ ] Snowflake 30-day trial account created; account identifier noted ← **YOU** (see `docs/phase0-foundation.md`)
- [ ] SnowSQL CLI installed; named connection `snowflake_pipeline` in `~/.snowsql/config` ← **YOU**
- [x] `sql/00_setup/*.sql` — idempotent: role, warehouse (XSMALL, auto-suspend 60s), database, schemas `RAW`/`STAGING`/`MARTS` *(written; config-driven via `config/pipeline.conf`)*
- [x] `scripts/deploy.sh` — rebuilds full env via SnowSQL, `--dry-run` supported *(written; dry-run verified offline)*
- [ ] **Acceptance:** `./scripts/deploy.sh` on a clean account produces the full layout *(blocked on trial account above)*

## Phase 1 — Snowpipe ingestion (files → RAW, incl. semi-structured)

- [x] Synthetic data generated as CSV **and** JSON *(`scripts/generate_synthetic_data.py`, stdlib, seeded, tested; Synthea-shaped stand-in — swap real Synthea before demo)*
- [x] External S3 stage + file format per type + RAW target tables *(`sql/10_ingest/00–03`, written)*
- [x] JSON landed into `VARIANT`; dot / lateral-flatten query examples *(`manual/flatten_queries.sql`)*
- [x] Snowpipe auto-ingest DDL + end-to-end docs *(`04_snowpipe.sql`, `docs/snowpipe-setup.md`)*
- [x] Manual `COPY INTO` fallback path *(`manual/copy_manual.sql`)*
- [x] Deliverables: `sql/10_ingest/`, `docs/snowpipe-setup.md`, sample files (`sql/10_ingest/samples/`), flatten queries
- [x] RAW tables + file formats created LIVE; encounters loaded via internal-stage COPY (`scripts/load_internal_stage.py`, no-AWS path); VARIANT dot-access + LATERAL FLATTEN verified LIVE (1023 encounters)
- [ ] **AWS side (auto-ingest only):** S3 bucket + IAM role + storage-integration trust + SQS event notification ← **YOU** (see `docs/snowpipe-setup.md`)
- [ ] **Acceptance (auto-ingest):** file dropped in S3 lands rows in RAW < 1 min, no manual step *(needs AWS; the COPY/VARIANT half is verified live)*

## Phase 2 — Relational source loader (Python)

- [x] Python job: extract from SQL Server → RAW *(`loader/`, pyodbc source + Snowflake sink, lazy-imported)*
- [x] Governance ported: versioning, structured logging, `--dry-run`, PII masking on load, `argparse` CLI, file locking *(all in `loader/`)*
- [x] Incremental/idempotent load via high-water-mark column *(`loader/watermark.py`, checkpoint-after-commit)*
- [x] Config-driven (table list, mappings); no secrets in code *(`config/loader.yaml` + offline `loader.sample.yaml`)*
- [x] Deliverables: `loader/` package, `config/loader.yaml`, unit tests, `docs/loader.md`
- [x] **Acceptance (offline):** `python -m loader --dry-run --config config/loader.sample.yaml` reports intended changes + masked sample, writes nothing — **verified**
- [x] **Acceptance (live):** verified against account fjliqhb-of64443 — 300 rows masked, re-run = 0 (watermark). Proven via file, SQLite, **AND a real local SQL Server 2025** (`SqlServerSource` + pyodbc/Windows auth; `config/loader.sqlserver.yaml`, `scripts/csv_to_sqlserver.py`).

## Phase 3 — Streams + Tasks → star schema (centerpiece)

- [x] Streams on RAW tables to capture change *(`00_streams.sql`, APPEND_ONLY, live)*
- [x] STAGING transforms (typing, dedup, flatten) *(`01_staging.sql` + `04_build.sql`, live)*
- [x] MARTS as star schema: fact + conformed dimensions *(`02`/`03`, live; FACT_ENCOUNTER 1024)*
- [x] One deliberately **snowflaked** dimension (location → facility → region) *(verified via live region rollup)*
- [x] Task DAG (root + dependents) on schedule: staging → marts *(`05_tasks.sql`, 10 tasks, live)*
- [x] SCD Type 2 on at least one dimension *(DIM_PATIENT; relocation test produced 2 versions live)*
- [x] Deliverables: `sql/30_transform/`, `docs/data-model.md`
- [x] **Acceptance (LIVE):** injected new patient+encounter → DAG propagated to FACT in **18s**; star + snowflake both queried; SCD2 history verified. *(bug caught+fixed live: SCD2 initial valid_from epoch; serverless→warehouse task grant)*
- [x] **Optional 3b (dbt): DONE + verified LIVE** — `dbt/` project, snapshot-based SCD2, 6 marts + 3 staging models in a separate `DBT` schema, 20 data tests (incl. referential integrity) all green (`PASS=30`). `docs/dbt.md`.

## Phase 4 — Snowpark transformation

- [x] Cohort aggregation (region × encounter_class) as Snowpark Python *(`snowpark/cohort_aggregation.py`)*
- [x] Written two ways: naive (client-side pandas) vs optimized (warehouse pushdown)
- [x] Deliverables: `snowpark/`, `docs/snowpark-optimization.md` (before/after)
- [x] **Acceptance (LIVE):** identical output both ways; optimized moves 206× less data to client (5 vs 1030 rows). *Honest caveat: wall-clock win needs a larger fact table — documented, not claimed.*

## Phase 5 — Performance tuning case study

- [x] Deliberately unclustered 2.05M-row fact; tuned via ordering on the filter column *(`scripts/perf_case_study.py`)*
- [x] Diagnosed via `GET_QUERY_OPERATOR_STATS` (partitions scanned) + `SYSTEM$CLUSTERING_INFORMATION` (depth)
- [x] Write-up: symptom → diagnosis → fix → measured result *(`docs/performance-case-study.md`)*
- [x] Deliverables: `docs/performance-case-study.md` with live before/after
- [x] **Acceptance (LIVE):** reproducible win — 15/15 → 2/16 partitions scanned (7.5×), depth 15.0 → 1.5

## Phase 6 — Docs, spec, demo

- [x] `docs/functional-spec.md` (requirements, sources, business questions)
- [x] `docs/technical-design.md` (architecture, data flow, RBAC, decisions + tradeoffs)
- [x] Real architecture diagram (mermaid flowchart in technical-design.md)
- [x] README: what it is, deploy from scratch, how to demo
- [x] `docs/demo-script.md` — 3–5 min end-to-end walkthrough
- [x] **Acceptance:** specs + demo script let a stranger deploy and understand from scratch

---

## Standing constraints (carry every session)

- Standalone / CLI only — **no web interface**.
- Data governance is first-class: RBAC, PII/PHI masking on load, `--dry-run` on destructive ops, structured logging. A dedicated `docs/governance.md` lands during Phases 2–3.
- No secrets in code or git history — env vars / SnowSQL config only.
- Every SQL deploy script idempotent and re-runnable.
- Flag assumptions with `# ASSUMPTION:` comments.
- Dev targets **WSL2 / Linux**; call out Windows-side steps (S3/SQS, SnowSQL config path) explicitly.
- Watch trial credits — warehouse `XSMALL`, aggressive auto-suspend.
- **Hard rule:** never reference "Columbia University," "CUIT," or that institution anywhere.

## Session log

- 2026-07-22 — Phase 0 repo skeleton built; private GitHub repo created + pushed; `PROGRESS.md` added.
- 2026-07-22 — **Relocated project to `C:\snowflake-pipeline`** (canonical local path). Old copy under the OneDrive-redirected Desktop churned/wiped local files mid-build; GitHub remote was the safety net. Do not work out of `C:\Users\matt\OneDrive\Desktop\files` — OneDrive folder redirection is active on this machine.
- 2026-07-22 — Phase 0 SQL + `deploy.sh` written, dry-run verified. `.gitattributes` added (LF for WSL2).
- 2026-07-22 — **Phase 1 pre-built offline** (no live Snowflake yet): generator + tests (4 green), `sql/10_ingest/` DDL, `manual/` copy+flatten, `docs/snowpipe-setup.md`, committed sample data. `deploy.sh` generalized with `--dir`. Live deploy + AWS S3/SQS wiring pending.
- 2026-07-22 — **Phase 2 built** (`loader/`, 15 tests green, offline dry-run works).
- 2026-07-22 — **LIVE account connected** (fjliqhb-of64443, ACCOUNTADMIN, AWS_CA_CENTRAL_1). Creds in `~/.snowflake/connections.toml` (outside repo). Added `scripts/run_sql.py` (connector-based deploy, no SnowSQL needed) + `scripts/load_internal_stage.py` (no-AWS PUT+COPY). **Verified LIVE:** Phase 0 full deploy; Phase 1 RAW tables + VARIANT/FLATTEN (1023 encounters); Phase 2 loader (300 patients, masked, incremental). Data via `data/synthea` (gitignored) + `config/loader.local.yaml` (gitignored).
- 2026-07-23 — **Taste refactor (5/5 pass).** Killed transform triplication: flatten/dedup in staging views, region/SCD2/fact-join in 2 stored procedures (`sp_ingest`, `sp_build_marts`) called by both backfill and tasks. Collapsed 10-task DAG → 2 (root `t_ingest` → `t_build_marts`); `run_sql.py` got a real `$$`-aware statement splitter. Removed `deploy.sh` (one deploy tool, no drift). Unified CLIs via `scripts/_cli.py` (shared `--connection/--database/--config`, single connection source) + `docs/configuration.md`. Loader retry+timeouts on connect. Removed positional `$1..$11` CSV coupling (MATCH_BY_COLUMN_NAME). All verified live: backfill idempotent, DAG 18s propagation, full run_pipeline 12/12, CI green, 19 tests.
- 2026-07-23 — **Hardening audit (harsh self-review).** Fixed: watermark corruption for numeric/timestamp HWM (client-side lexicographic compare → now takes last ASC row, native type); watermark type drift (str-coercion → native/ISO); masking crash on non-string DB values; file-source empty-file crash; SQL-injection surface (identifier allowlist on table/column names); perf-study storage leak (drop in finally); cursor leak; dead import. Documented at-least-once landing semantics + other caveats in docs/loader.md. 19 tests green; SQL Server + Snowpark re-verified live.
- 2026-07-23 — **Real SQL Server verified LIVE.** Local SQL Server 2025 (default instance, Windows auth). `scripts/csv_to_sqlserver.py` seeds HEALTH_SOURCE.dbo.patients (300 rows); `loader/source_sqlserver.py` via pyodbc/Driver 18 → RAW, masked, incremental (re-run=0). Fixed a real bug: dry-run never connected the source (only file source, which opens lazily, had worked). SQL Server source gap CLOSED — only AWS S3 auto-ingest remains.
- 2026-07-23 — **Beyond the plan, all verified LIVE:** MARTS analytics/BI views (5); data-quality gate (`scripts/data_quality.py`, 12/12 pass); SQLite relational source (`loader/source_sqlite.py`, real DB engine, 300 rows loaded); GitHub Actions CI (green on push); **dbt project (Phase 3b)** — `dbt build` PASS=30/0 errors with snapshot SCD2 + 20 data tests.
- 2026-07-22 — **Phase 3 built + verified LIVE.** `sql/30_transform/` (streams, staging, dims, fact, backfill, 10-task DAG) + `docs/data-model.md`. Star + snowflaked DIM_LOCATION + SCD2 DIM_PATIENT. Two live-caught bugs fixed: SCD2 initial `valid_from` must be epoch (else historical encounters get null patient_sk); child tasks need `WAREHOUSE=` (or EXECUTE MANAGED TASK) — both now set + granted. DAG root left SUSPENDED to save credits (resume: `ALTER TASK staging.t_stage_patients RESUME`). Left-over demo rows in RAW (PAT-000301, ENC-DAGTEST01, PAT-000001 relocated) are harmless.
