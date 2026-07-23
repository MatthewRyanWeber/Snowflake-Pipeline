"""Build a SQLite database from a CSV, so the loader has a real relational source to read.

Usage:
  python scripts/csv_to_sqlite.py --csv data/synthea/patients.csv --db data/synthea/patients.db --table patients
"""

import argparse
import csv
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("csv_to_sqlite")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Load a CSV into a SQLite table.")
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--table", default="patients")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    with args.csv.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        logger.error("no rows in %s", args.csv)
        return 1
    cols = list(rows[0].keys())

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(args.db))
    try:
        con.execute(f"DROP TABLE IF EXISTS {args.table}")
        con.execute(f"CREATE TABLE {args.table} ({', '.join(c + ' TEXT' for c in cols)})")
        con.executemany(
            f"INSERT INTO {args.table} ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        con.commit()
        n = con.execute(f"SELECT COUNT(*) FROM {args.table}").fetchone()[0]
    finally:
        con.close()
    logger.info("wrote %d rows -> %s (%s)", n, args.db, args.table)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
