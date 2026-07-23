# PROGRESS — Snowflake Pipeline

Durable, git-tracked build status. The source of truth for resuming across sessions.
Full detail lives in [`PLAN.md`](PLAN.md); conventions in [`CLAUDE.md`](CLAUDE.md).

**To resume:** open this file, find the first unchecked box, say "continue with Phase N."

---

## Overall status

| Phase | Title | Status |
|---|---|---|
| 0 | Foundation | 🟡 Scripts written + dry-run verified; live deploy pending trial account |
| 1 | Snowpipe ingestion (files → RAW) | 🟡 Pre-built offline; live deploy + AWS S3/SQS pending |
| 2 | Relational source loader (Python) | 🟡 Built + 15 tests green + offline dry-run works; live SQL Server pending |
| 3 | Streams + Tasks → star schema | ⬜ Not started |
| 4 | Snowpark transformation | ⬜ Not started |
| 5 | Performance tuning case study | ⬜ Not started |
| 6 | Docs, spec, demo | ⬜ Not started |

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
- [ ] **AWS side:** S3 bucket + IAM role + storage-integration trust + SQS event notification ← **YOU** (see `docs/snowpipe-setup.md`)
- [ ] **Acceptance:** file dropped in S3 lands rows in RAW < 1 min, no manual step; JSON queryable via VARIANT *(blocked on live account + AWS above)*

## Phase 2 — Relational source loader (Python)

- [x] Python job: extract from SQL Server → RAW *(`loader/`, pyodbc source + Snowflake sink, lazy-imported)*
- [x] Governance ported: versioning, structured logging, `--dry-run`, PII masking on load, `argparse` CLI, file locking *(all in `loader/`)*
- [x] Incremental/idempotent load via high-water-mark column *(`loader/watermark.py`, checkpoint-after-commit)*
- [x] Config-driven (table list, mappings); no secrets in code *(`config/loader.yaml` + offline `loader.sample.yaml`)*
- [x] Deliverables: `loader/` package, `config/loader.yaml`, unit tests, `docs/loader.md`
- [x] **Acceptance (offline):** `python -m loader --dry-run --config config/loader.sample.yaml` reports intended changes + masked sample, writes nothing — **verified**
- [ ] **Acceptance (live):** real SQL Server run incremental + re-runnable, no dupes; masked columns land masked *(pending live DB + account)*

## Phase 3 — Streams + Tasks → star schema (centerpiece)

- [ ] Streams on RAW tables to capture change
- [ ] STAGING transforms (typing, dedup, conformance) consuming streams
- [ ] MARTS as star schema: fact table(s) + conformed dimensions
- [ ] One deliberately **snowflaked** dimension (location → facility → region)
- [ ] Task DAG (root + dependents) on schedule: staging → marts
- [ ] SCD Type 2 on at least one dimension
- [ ] Deliverables: `sql/30_transform/`, `docs/data-model.md` (ER diagram)
- [ ] **Acceptance:** raw rows flow automatically streams → staging → marts on schedule; star + snowflake both queryable; SCD2 history verifiable
- [ ] *(Optional 3b: rebuild STAGING→MARTS as dbt models with tests + lineage)*

## Phase 4 — Snowpark transformation

- [ ] One non-trivial transform (e.g. patient-cohort aggregation) as Snowpark Python
- [ ] Written two ways: naive vs optimized (predicate pushdown, minimize collect/materialize, right-sized warehouse)
- [ ] Deliverables: `snowpark/`, `docs/snowpark-optimization.md` (before/after)
- [ ] **Acceptance:** identical output both ways; optimized shows measurably less compute in query history

## Phase 5 — Performance tuning case study

- [ ] Take one deliberately slow query/table; tune it (clustering key, micro-partition pruning, warehouse sizing, result caching, avoid spillage)
- [ ] Diagnose via Query Profile + `QUERY_HISTORY` / `WAREHOUSE_LOAD_HISTORY`
- [ ] Write-up: symptom → diagnosis → fix → measured result
- [ ] Deliverables: `docs/performance-case-study.md` (profiles + before/after timings + credit usage)
- [ ] **Acceptance:** documented, reproducible tuning win walkable in 3–4 min

## Phase 6 — Docs, spec, demo

- [ ] `docs/functional-spec.md` (requirements, sources, business questions)
- [ ] `docs/technical-design.md` (architecture, data flow, RBAC, decisions + tradeoffs)
- [ ] Real architecture diagram (upgrade the ASCII)
- [ ] README: what it is, deploy from scratch, how to demo
- [ ] 3–5 min demo script (or Loom) end to end
- [ ] **Acceptance:** stranger clones, reads specs, understands in 10 min; live demo from clean deploy

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
