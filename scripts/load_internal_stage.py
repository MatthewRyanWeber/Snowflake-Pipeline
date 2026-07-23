#!/usr/bin/env python3
"""Load a local file into a RAW table via a Snowflake INTERNAL stage (PUT + COPY).

The no-AWS ingestion path: same COPY semantics as Snowpipe, but the file is uploaded
straight to an internal stage instead of landing in S3. Useful for local testing/demos
before (or without) wiring up S3 auto-ingest.

Usage:
  python -m scripts.load_internal_stage --file data/synthea/encounters.json \
      --table ENCOUNTERS_JSON --format json
  python -m scripts.load_internal_stage --file data/synthea/patients.csv \
      --table PATIENTS_CSV --format csv
"""

import argparse
import logging
import sys
from pathlib import Path

from . import _cli

logger = logging.getLogger("load_internal_stage")

# Per-format COPY body. CSV matches columns by NAME (order-independent); JSON lands the whole
# object into the VARIANT column. Mirrors sql/10_ingest/04_snowpipe.sql.
def _copy_body(fmt: str, table: str, stage: str, fmt_name: str, pattern: str) -> str:
    if fmt == "csv":
        return (
            f"COPY INTO {table} FROM @{stage}\n"
            f"FILE_FORMAT = (FORMAT_NAME = {fmt_name})\n"
            f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE\n"
            f"INCLUDE_METADATA = (_source_file = METADATA$FILENAME)\n"
            f"PATTERN = '{pattern}'\nON_ERROR = 'ABORT_STATEMENT'"
        )
    return (
        f"COPY INTO {table} (v, _source_file, _file_row)\n"
        f"FROM (SELECT $1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER FROM @{stage})\n"
        f"FILE_FORMAT = (FORMAT_NAME = {fmt_name})\n"
        f"PATTERN = '{pattern}'\nON_ERROR = 'ABORT_STATEMENT'"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Load a local file into RAW via an internal stage.")
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--table", required=True, help="target RAW table, e.g. ENCOUNTERS_JSON")
    p.add_argument("--format", choices=["csv", "json"], required=True)
    p.add_argument("--schema", default="RAW")
    p.add_argument("--stage", default="LOCAL_STAGE")
    p.add_argument("--truncate", action="store_true", help="TRUNCATE target before loading")
    _cli.add_common_args(p)
    args = p.parse_args(argv)

    _cli.setup_logging(args.verbose)
    if not args.file.exists():
        logger.error("file not found: %s", args.file)
        return 1

    import snowflake.connector as sc

    fmt_name = f"{args.schema}.{args.format}_format"
    posix = args.file.resolve().as_posix()  # PUT wants forward slashes, even on Windows
    name = _cli.read_connection_name(args.config, args.connection)
    con = sc.connect(connection_name=name, database=args.database, schema=args.schema)
    cur = con.cursor()
    try:
        cur.execute(f"USE SCHEMA {args.database}.{args.schema}")
        cur.execute(f"CREATE STAGE IF NOT EXISTS {args.stage} "
                    f"COMMENT='Internal stage for local (no-S3) loads'")
        if args.truncate:
            cur.execute(f"TRUNCATE TABLE {args.table}")
            logger.info("truncated %s", args.table)

        logger.info("PUT %s -> @%s", args.file.name, args.stage)
        cur.execute(f"PUT 'file://{posix}' @{args.stage} OVERWRITE=TRUE AUTO_COMPRESS=TRUE")

        copy_sql = _copy_body(args.format, args.table, args.stage, fmt_name,
                              f".*{args.file.stem}.*")
        cur.execute(copy_sql)
        loaded = cur.fetchall()
        total = cur.execute(f"SELECT COUNT(*) FROM {args.table}").fetchone()[0]
        logger.info("COPY result rows: %s", loaded)
        logger.info("%s now has %d row(s)", args.table, total)
    finally:
        cur.close()
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
