# PROGRESS — Snowflake Pipeline

Durable, git-tracked build status. The source of truth for resuming across sessions.
Full detail lives in [`PLAN.md`](PLAN.md); conventions in [`CLAUDE.md`](CLAUDE.md).

**To resume:** open this file, find the first unchecked box, say "continue with Phase N."

---

## Overall status

| Phase | Title | Status |
|---|---|---|
| 0 | Foundation | 🟡 In progress (repo done; Snowflake env pending) |
| 1 | Snowpipe ingestion (files → RAW) | ⬜ Not started |
| 2 | Relational source loader (Python) | ⬜ Not started |
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
- [ ] Snowflake 30-day trial account created; account identifier noted
- [ ] SnowSQL CLI installed; named connection configured (no hardcoded creds)
- [ ] `sql/00_setup/*.sql` — idempotent: role, warehouse (XSMALL, auto-suspend 60s), database, schemas `RAW`/`STAGING`/`MARTS`
- [ ] `scripts/deploy.sh` — rebuilds full env via SnowSQL, zero manual clicks
- [ ] **Acceptance:** `./scripts/deploy.sh` on a clean account produces the full layout

## Phase 1 — Snowpipe ingestion (files → RAW, incl. semi-structured)

- [ ] Synthea synthetic data generated as CSV **and** JSON
- [ ] External S3 stage + file format per type + RAW target tables
- [ ] JSON landed into `VARIANT`; dot / lateral-flatten query examples
- [ ] Snowpipe auto-ingest configured (S3 event → SQS), documented end to end
- [ ] Manual `COPY INTO` fallback path for troubleshooting demos
- [ ] Deliverables: `sql/10_ingest/`, `docs/snowpipe-setup.md`, sample files, flatten queries
- [ ] **Acceptance:** file dropped in S3 lands rows in RAW < 1 min, no manual step; JSON queryable via VARIANT

## Phase 2 — Relational source loader (Python)

- [ ] Python job: extract from SQL Server (or Postgres) → RAW via Snowflake connector / Snowpark write
- [ ] Governance ported: versioning, structured logging, `--dry-run`, PII masking on load, `argparse` CLI, file locking
- [ ] Incremental/idempotent load via high-water-mark column
- [ ] Config-driven (table list, mappings); no secrets in code
- [ ] Deliverables: `loader/` package, `config/loader.yaml`, unit tests, `docs/loader.md`
- [ ] **Acceptance:** `python -m loader --dry-run` reports intended changes; real run incremental + re-runnable, no dupes; masked columns land masked

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
