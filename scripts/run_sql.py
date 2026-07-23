#!/usr/bin/env python3
"""The deploy tool: run phase SQL via the Snowflake Python connector (no SnowSQL install).

Reads config/pipeline.conf, substitutes SnowSQL-style &{var} placeholders, and runs every
top-level *.sql in a directory in filename order. Handles stored-procedure bodies ($$...$$).
Credentials come from the named connection in ~/.snowflake/connections.toml — never here.

Usage:
  python -m scripts.run_sql --dir sql/00_setup [--dry-run] [--connection NAME]
  python -m scripts.run_sql --file sql/00_setup/99_validate.sql
"""

import argparse
import logging
import re
import sys
from pathlib import Path

from . import _cli

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


def split_statements(sql: str) -> list:
    """Split a script into statements on top-level ';', ignoring semicolons inside
    single-quoted strings and $$...$$ dollar-quoted blocks (stored-procedure bodies).

    The connector's execute_string splits naively and breaks on procedure bodies; this
    is the robust replacement so CREATE PROCEDURE ... $$ ... ; ... $$ stays one statement.
    """
    stmts, buf = [], []
    i, n = 0, len(sql)
    in_squote = in_dollar = False
    while i < n:
        ch = sql[i]
        pair = sql[i:i + 2]
        if in_dollar:
            buf.append(ch)
            if pair == "$$":
                buf.append("$")
                i += 2
                in_dollar = False
                continue
            i += 1
        elif in_squote:
            buf.append(ch)
            if ch == "'":
                if sql[i + 1:i + 2] == "'":       # escaped '' inside a string
                    buf.append("'")
                    i += 2
                    continue
                in_squote = False
            i += 1
        elif pair == "$$":
            buf.append("$$")
            i += 2
            in_dollar = True
        elif ch == "'":
            buf.append(ch)
            i += 1
            in_squote = True
        elif pair == "--":                          # line comment -> copy to EOL
            eol = sql.find("\n", i)
            eol = n if eol == -1 else eol
            buf.append(sql[i:eol])
            i = eol
        elif ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def run_file(con, path: Path, variables: dict, dry_run: bool) -> None:
    sql = substitute(path.read_text(encoding="utf-8"), variables)
    statements = split_statements(sql)
    logger.info("--- %s (%d statement(s))", path.name, len(statements))
    if dry_run:
        print(sql)
        return
    cur = con.cursor()
    try:
        for stmt in statements:
            cur.execute(stmt)
            if cur.description:  # a result-producing statement (SELECT/SHOW/DESC/CALL)
                rows = cur.fetchall()
                cols = [c[0] for c in cur.description]
                for r in rows[:20]:
                    print("   ", dict(zip(cols, r)))
    finally:
        cur.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run phase SQL via the Snowflake connector.")
    p.add_argument("--dir", type=Path, help="directory of *.sql to run in order")
    p.add_argument("--file", type=Path, help="single .sql file to run")
    p.add_argument("--dry-run", action="store_true")
    _cli.add_common_args(p)
    args = p.parse_args(argv)

    _cli.setup_logging(args.verbose)

    if not args.dir and not args.file:
        p.error("give --dir or --file")

    conf = read_conf(args.config)
    variables = build_vars(conf)
    connection_name = _cli.read_connection_name(args.config, args.connection)

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
