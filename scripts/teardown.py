#!/usr/bin/env python3
"""Tear down every object this pipeline created — clean uninstall / reset.

Drops the database (cascades to schemas, tables, streams, tasks, stages), the warehouse,
and the role. Requires ACCOUNTADMIN. Guarded by --yes so it can't run by accident.

Run:  python scripts/teardown.py --yes
"""

import argparse
import logging
import sys

import snowflake.connector as sc

logger = logging.getLogger("teardown")

DROPS = [
    "USE ROLE ACCOUNTADMIN",
    "DROP DATABASE IF EXISTS HEALTH_ANALYTICS",   # cascades: schemas, tables, streams, tasks, stages
    "DROP WAREHOUSE IF EXISTS PIPELINE_WH",
    "DROP ROLE IF EXISTS PIPELINE_ROLE",
]


def main() -> int:
    p = argparse.ArgumentParser(description="Drop all pipeline objects.")
    p.add_argument("--yes", action="store_true", help="confirm the destructive teardown")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if not args.yes:
        logger.error("refusing to drop objects without --yes")
        return 2

    con = sc.connect(connection_name="snowflake_pipeline")
    cur = con.cursor()
    try:
        for stmt in DROPS:
            cur.execute(stmt)
            logger.info("ok: %s", stmt)
    finally:
        cur.close()
        con.close()
    logger.info("teardown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
