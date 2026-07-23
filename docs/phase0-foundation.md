# Phase 0 — Foundation

Rebuilds the entire Snowflake environment (role, warehouse, database, schemas) from
scratch with one command. Every script is idempotent — re-running changes nothing.

## What gets created

| Object | Name | Notes |
|---|---|---|
| Role | `PIPELINE_ROLE` | Functional role, parented under `SYSADMIN`, granted to the deployer. |
| Warehouse | `PIPELINE_WH` | `XSMALL`, auto-suspend 60s, initially suspended (protects trial credits). |
| Database | `HEALTH_ANALYTICS` | Owned by `PIPELINE_ROLE`. |
| Schemas | `RAW`, `STAGING`, `MARTS` | The three-layer flow from `PLAN.md`. |

Names live in [`config/pipeline.conf`](../config/pipeline.conf) — nothing is hardcoded in
the SQL. Change a name there and re-deploy.

## Prerequisites (you-side, one time)

1. **Snowflake trial** — sign up (30-day free) and note the *account identifier*
   (e.g. `abcd-xy12345`). You'll be `ACCOUNTADMIN`.
2. **SnowSQL CLI** — install it, then add a named connection to `~/.snowsql/config`.
   The connection name must match `SF_CONNECTION` in `config/pipeline.conf`
   (default `snowflake_pipeline`):

   ```ini
   [connections.snowflake_pipeline]
   accountname = <your_account_identifier>
   username    = <your_user>
   # Do NOT store the password here in plaintext for anything real.
   # Prefer key-pair auth or an env var: export SNOWSQL_PWD=...
   ```

   > **Windows note:** SnowSQL config lives at `%USERPROFILE%\.snowsql\config`. This project
   > runs `deploy.sh` under WSL2/Linux, where the path is `~/.snowsql/config`. Keep the
   > connection in whichever environment you run the script from.

   Credentials never go in this repo — `.gitignore` already excludes `.snowsql/`, `.env`, keys.

## Deploy

```bash
# Preview only — prints the resolved SnowSQL commands, executes nothing:
scripts/deploy.sh --dry-run

# Real run:
scripts/deploy.sh                      # uses SF_CONNECTION from config
scripts/deploy.sh --connection my_conn # or override the connection
```

The script runs `sql/00_setup/*.sql` in numeric order and stops on the first error.

## Acceptance criteria

- `scripts/deploy.sh` on a clean account produces the full role/warehouse/schema layout
  with zero manual clicks.
- `99_validate.sql` (run last) reports `CURRENT_ROLE = PIPELINE_ROLE`,
  `CURRENT_WAREHOUSE = PIPELINE_WH`, `CURRENT_DATABASE = HEALTH_ANALYTICS`, and lists the
  three schemas.
- Re-running the deploy is a no-op (idempotent).

## Status

SQL + `deploy.sh` written and dry-run-verified offline. **Live-deploy verification is
pending a Snowflake trial account + SnowSQL connection** (the prerequisites above).
