#!/usr/bin/env python3
"""Load a CSV into a local SQL Server table, so the loader has a real SQL Server source.

Creates the database + table if needed (Windows/trusted auth by default). Companion to
csv_to_sqlite.py. No password stored anywhere — uses Trusted_Connection.

Usage:
  python -m scripts.csv_to_sqlserver --csv data/synthea/patients.csv \
      --database HEALTH_SOURCE --table patients
"""

import argparse
import csv
import logging
from pathlib import Path

import pyodbc

logger = logging.getLogger("csv_to_sqlserver")


def conn_str(database: str, server: str, driver: str) -> str:
    return (f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            "Trusted_Connection=yes;TrustServerCertificate=yes")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--database", default="HEALTH_SOURCE")
    p.add_argument("--table", default="patients")
    p.add_argument("--server", default="localhost")
    p.add_argument("--driver", default="ODBC Driver 18 for SQL Server")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    with args.csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        logger.error("no rows in %s", args.csv)
        return 1
    cols = list(rows[0].keys())

    # 1. Create the database (autocommit — CREATE DATABASE can't run in a txn).
    master = pyodbc.connect(conn_str("master", args.server, args.driver), autocommit=True)
    master.cursor().execute(
        f"IF DB_ID('{args.database}') IS NULL EXEC('CREATE DATABASE [{args.database}]')")
    master.close()

    # 2. Create the table + load rows.
    con = pyodbc.connect(conn_str(args.database, args.server, args.driver))
    cur = con.cursor()
    cur.execute(f"IF OBJECT_ID('dbo.{args.table}','U') IS NOT NULL DROP TABLE dbo.{args.table}")
    coldefs = ", ".join(f"[{c}] NVARCHAR(200)" for c in cols)
    cur.execute(f"CREATE TABLE dbo.{args.table} ({coldefs})")
    placeholders = ", ".join("?" * len(cols))
    cur.fast_executemany = True
    cur.executemany(
        f"INSERT INTO dbo.{args.table} ({', '.join('['+c+']' for c in cols)}) VALUES ({placeholders})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    con.commit()
    n = cur.execute(f"SELECT COUNT(*) FROM dbo.{args.table}").fetchone()[0]
    con.close()
    logger.info("loaded %d rows -> SQL Server %s.dbo.%s", n, args.database, args.table)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
