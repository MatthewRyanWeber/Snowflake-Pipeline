# Ingestion sources

The loader extracts from any source that implements one small contract — `connect()`,
`count()`, `fetch_batches(table, hwm_column, since, batch_size)`, `close()` — so **adding or
switching a source is a `source.type` change in config, not a code change**. Every source is
incremental (high-water-mark) and checkpointed: a crash resumes from the last committed batch.

| `source.type` | Backend | Driver | Streaming | Status | Example config |
|---|---|---|---|---|---|
| `sqlserver` | SQL Server | pyodbc | server cursor | verified live | `config/loader.sqlserver.yaml` |
| `postgres` | PostgreSQL | psycopg2 | server-side named cursor | **verified live (Docker)** | `config/loader.postgres.yaml` |
| `mysql` | MySQL / MariaDB | PyMySQL | unbuffered `SSDictCursor` | **verified live (Docker)** | `config/loader.mysql.yaml` |
| `oracle` | Oracle | oracledb (thin) | array fetch | wired, unit-tested | `config/loader.oracle.yaml` |
| `sqlite` | SQLite | stdlib | cursor fetchmany | verified live | `config/loader.sqlite.yaml` |
| `rest` | REST API (JSON/HTTP) | requests | limit/offset paging | verified (unit test) | `config/loader.rest.yaml` |
| `excel` | Excel `.xlsx` | openpyxl | read-only sheet iter | verified (unit test) | `config/loader.excel.yaml` |
| `parquet` | Parquet file | pyarrow | Arrow batch slices | verified (unit test) | `config/loader.parquet.yaml` |
| `file` | CSV file | stdlib | row slices | verified live | `config/loader.local.yaml` |

Run any of them the same way:

```bash
python -m loader --config config/loader.postgres.yaml          # or --dry-run first
```

Secrets never live in config: database passwords come from an environment variable named by
`password_env` (default `PGPASSWORD` / `MYSQL_PASSWORD` / `ORACLE_PASSWORD`), and the REST
bearer token from `token_env`.

## Verifying Postgres and MySQL live (Docker)

These two need a running server, so they're verified against throwaway containers rather than a
unit test. Reproduce it:

```bash
# 1. Start the databases
docker run -d --name sfpg    -e POSTGRES_PASSWORD=Test123 -e POSTGRES_DB=srcdb -p 55432:5432 postgres:16-alpine
docker run -d --name sfmysql -e MYSQL_ROOT_PASSWORD=Test123 -e MYSQL_DATABASE=srcdb -p 33306:3306 mysql:8.4

# 2. Seed a table (both accept the same INSERTs)
docker exec sfpg    psql -U postgres -d srcdb -c \
  "CREATE TABLE patients(id INT,name TEXT,ssn TEXT,ts INT); \
   INSERT INTO patients VALUES (1,'a','111-11-1111',10),(2,'b','222-22-2222',20),(3,'c','333-33-3333',30),(4,'d','444-44-4444',40);"

# 3. Extract through the loader's source (count + full + incremental)
PGPASSWORD=Test123 python -c "from loader.source_postgres import PostgresSource as S; \
  s=S(host='127.0.0.1',port=55432,dbname='srcdb',user='postgres').connect(); \
  print('count', s.count('patients','ts',None)); \
  print('since>20', [r['id'] for b in s.fetch_batches('patients','ts',20,10) for r in b])"

# 4. Tear down
docker rm -f sfpg sfmysql
```

Observed: `count 4`, full load returns ids `[1,2,3,4]` in ascending hwm order, incremental
(`since=20`) returns `[3,4]` — identical results for both engines.

## The file-based and REST sources

`rest`, `excel`, and `parquet` are covered by `tests/test_sources.py` (run with
`python -m pytest tests/ -q`): each asserts count, full load in ascending hwm order, batching,
and the incremental `since` filter. The REST test stands up a real local HTTP server and pages
through it; the Parquet test writes an intentionally unsorted file to prove the source sorts by
the high-water-mark before batching.
