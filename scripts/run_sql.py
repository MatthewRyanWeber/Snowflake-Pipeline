#!/usr/bin/env python3
"""Run phase SQL via the Snowflake Python connector (no SnowSQL install needed).

Mirrors scripts/deploy.sh: reads config/pipeline.conf, substitutes SnowSQL-style
&{var} placeholders, and runs every top-level *.sql in a directory in filename order.
Credentials come from the named connection in ~/.snowflake/connections.toml — never here.

Usage:
  python scripts/run_sql.py --dir sql/00_setup [--dry-run] [--config config/pipeline.conf]
  python scripts/run_sql.py --file sql/00_setup/99_validate.sql
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("run_sql")

VAR_RE = re.compile(r"&\{(\w+)\}")


def read_conf(path: Path) -> dict:
    conf = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        conf[key.strip()] = val.strip()
    return conf


def build_vars(conf: dict) -> dict:
    # SnowSQL var name = lowercased config key; SF_CONNECTION is not a SQL variable.
    return {k.lower(): v for k, v in conf.items() if k.startswith("SF_") and k != "SF_CONNECTION"}


def substitute(sql: str, variables: dict) -> str:
    def repl(m):
        name = m.group(1)
        if name not in variables:
            raise KeyError(f"no value for &{{{name}}} in config")
        return variables[name]
    return VAR_RE.sub(repl, sql)


def run_file(con, path: Path, variables: dict, dry_run: bool) -> None:
    sql = substitute(path.read_text(encoding="utf-8"), variables)
    logger.info("--- %s", path.name)
    if dry_run:
        print(sql)
        return
    # execute_string splits and runs the multi-statement script in one session.
    for cur in con.execute_string(sql, remove_comments=False):
        if cur.description:  # a result-producing statement (SELECT/SHOW/DESC)
            rows = cur.fetchall()
            cols = [c[0] for c in cur.description]
            logger.info("  %s -> %d row(s)", (cur.query or "").split("\n")[0][:60], len(rows))
            for r in rows[:20]:
                print("   ", dict(zip(cols, r)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run phase SQL via the Snowflake connector.")
    p.add_argument("--dir", type=Path, help="directory of *.sql to run in order")
    p.add_argument("--file", type=Path, help="single .sql file to run")
    p.add_argument("--config", type=Path, default=Path("config/pipeline.conf"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if not args.dir and not args.file:
        p.error("give --dir or --file")

    conf = read_conf(args.config)
    variables = build_vars(conf)
    connection_name = conf.get("SF_CONNECTION", "snowflake_pipeline")

    files = [args.file] if args.file else sorted(args.dir.glob("*.sql"))
    if not files:
        logger.error("no .sql files found")
        return 1

    con = None
    try:
        if not args.dry_run:
            import snowflake.connector as sc
            con = sc.connect(connection_name=connection_name)
            logger.info("connected via '%s'", connection_name)
        for f in files:
            run_file(con, f, variables, args.dry_run)
    finally:
        if con is not None:
            con.close()
    logger.info("done (%d file(s))%s", len(files), " [dry-run]" if args.dry_run else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
