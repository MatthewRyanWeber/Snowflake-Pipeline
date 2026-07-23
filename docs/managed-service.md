# Running as a managed service

The pipeline is built to run as a service, not from a laptop. Three moving parts, and where
each runs:

| Part | Runs where | Managed by |
|---|---|---|
| Transform, orchestration, governance, audit | **Inside Snowflake** | Snowflake (Tasks, Dynamic Tables, masking policies, `GOV.LOAD_LOG`) |
| Deploy of the native objects | **GitHub Actions** | `.github/workflows/deploy.yml` |
| Connector (extract from source DB → RAW) | **A host with source access** | container / scheduler (see below) |

## Environment separation (dev / prod)

The deploy is parameterized by config. Each environment is a separate Snowflake database:

```bash
python -m scripts.run_sql --dir sql/00_setup --config config/pipeline.dev.conf    # HEALTH_ANALYTICS_DEV
python -m scripts.run_sql --dir sql/00_setup --config config/pipeline.prod.conf   # HEALTH_ANALYTICS
```

Verified live: deploying with `pipeline.dev.conf` builds a fully separate `HEALTH_ANALYTICS_DEV`
database with its own RAW/STAGING/MARTS. Prod is untouched.

## CI/CD deploys (not from a laptop)

`.github/workflows/deploy.yml` is a manual (`workflow_dispatch`) job that deploys the whole
native stack to a chosen environment. It uses a **GitHub Environment** (`dev` / `prod`) that
holds the secrets and can require an approval before prod.

Set these secrets per environment (Settings → Environments → dev/prod → Secrets):

- `SNOWFLAKE_ACCOUNT` (e.g. `myorg-myaccount`)
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD` (prefer key-pair auth for real prod)

Then: Actions → **deploy** → Run workflow → pick `dev` or `prod`. The job writes
`~/.snowflake/connections.toml` from the secrets and runs the deploy. Credentials never touch
the repo.

## Connector (the one external piece)

The connector extracts rows from a source database, so it must run **where it can reach the
source**. Options:

- **Cloud source** (reachable from CI/cloud): run the container on a scheduler — a K8s CronJob,
  ECS/Fargate scheduled task, or a scheduled GitHub Actions job — mounting the Snowflake creds.
- **On-prem / local source** (e.g. a SQL Server behind a firewall): run the same container on a
  small agent inside that network on a cron. GitHub-hosted runners cannot reach it, and neither
  can Snowflake — this is true of every Snowflake pipeline, not a limitation of this one.

Build and run the connector:

```bash
docker build -t snowflake-pipeline-connector .
docker run --rm \
  -v $HOME/.snowflake:/root/.snowflake:ro \
  snowflake-pipeline-connector --config config/loader.control.yaml
```

The connector reads its table work-list from the `GOV.SOURCES` control table (metadata-driven),
so adding a table to the schedule is an `INSERT`, not a redeploy.

## Operations

- **Cost:** `RESOURCE MONITOR PIPELINE_RM` caps credits and suspends before overspend.
- **Health:** `GOV.vw_pipeline_health` (per-target load history) and `GOV.task_failure_alert`.
- **Audit:** `GOV.LOAD_LOG` + native `COPY_HISTORY` / `ACCESS_HISTORY`.
- **Governance:** Dynamic Data Masking policies + `PII_READER` role; tag a new PII column to
  cover it automatically.
