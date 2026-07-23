# Configuration map

Where every piece of config lives and what governs what. There is one connection *name*
(`snowflake_pipeline`) and one place that resolves it; credentials live outside the repo.

## Connection resolution (one rule, everywhere)

Every connector-based script resolves the Snowflake connection the same way, via
`scripts/_cli.py`:

1. `--connection NAME` flag, if given; else
2. `SF_CONNECTION` in `config/pipeline.conf`; else
3. the default `snowflake_pipeline`.

The *name* points at a credential block. The credentials themselves are never in the repo.

## What each file governs

| File | In repo? | Governs |
|---|---|---|
| `config/pipeline.conf` | yes (no secrets) | Object **names** (role, warehouse, DB, schemas, S3) + `SF_CONNECTION`. Consumed by `run_sql.py` for `&{var}` substitution and by `_cli` for the default connection. |
| `config/loader.yaml` (+ `*.local.yaml`, `loader.sqlite.yaml`, `loader.sqlserver.yaml`) | yes (no secrets) | The **loader**: source type + tables + masking. References the connection by name under `snowflake.connection`. |
| `~/.snowflake/connections.toml` | **no** (home dir) | Snowflake **credentials** for the Python connector, keyed by connection name. |
| `~/.dbt/profiles.yml` | **no** (home dir) | Snowflake **credentials** for dbt (`dbt/profiles.example.yml` is the committed template). |

## Rule

Names and non-secret settings live in the repo (`config/`). Secrets live in your home
directory (`connections.toml`, `profiles.yml`), which `.gitignore` and location keep out of
git. If you change the connection name, change it in `config/pipeline.conf` and your
`connections.toml` / `profiles.yml` — nothing else.
