"""CLI entrypoint:  python -m loader [--dry-run] [--config PATH] [--table NAME] [--verbose]

--dry-run reports intended row counts + a masked sample without writing anything.
A real run is incremental (high-water-mark) and safe to re-run without duplicates.
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path

from . import __version__
from .config import load_config
from .lock import FileLock, LockHeldError
from .logging_config import configure
from .masking import DEFAULT_SALT
from .pipeline import load_table, run
from .watermark import WatermarkStore

logger = logging.getLogger("loader")


def _load_one(cfg, sf, table_cfg, watermarks, salt, run_id, src_label):
    """Load one table with its own source + sink connection — thread-safe for parallel loads."""
    from .sink_snowflake import SnowflakeSink
    source = _build_source(cfg).connect()
    sink = SnowflakeSink(sf["connection"], sf["database"], sf["schema"]).connect()
    try:
        res = load_table(source, sink, watermarks, table_cfg, salt, dry_run=False)
        sink.log_transfer(run_id, src_label, res.table, res.rows_read, res.rows_written)
        return res
    finally:
        sink.close()
        source.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="loader", description="SQL Server -> Snowflake RAW loader")
    p.add_argument("--config", type=Path, default=Path("config/loader.yaml"))
    p.add_argument("--dry-run", action="store_true", help="report intended changes, write nothing")
    p.add_argument("--table", action="append", help="limit to named table(s); repeatable")
    p.add_argument("--state", type=Path, default=Path("state/watermarks.json"))
    p.add_argument("--max-workers", type=int, default=8, help="parallel table-load workers")
    p.add_argument("--no-parallel", action="store_true", help="load tables sequentially")
    p.add_argument("--restart", action="store_true",
                   help="ignore saved checkpoints and reload the target table(s) from scratch")
    p.add_argument("--status", action="store_true",
                   help="print the resume checkpoint for each table and exit (no load)")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"loader {__version__}")
    args = p.parse_args(argv)

    configure(verbose=args.verbose)
    cfg = load_config(args.config)

    salt = cfg.get("masking", {}).get("salt", DEFAULT_SALT)
    sf = cfg["snowflake"]

    # Metadata-driven: read the work-list from GOV.SOURCES if a control group is configured;
    # otherwise use the tables listed in the config file.
    if cfg.get("control"):
        from .control import load_tables_from_control
        tables = load_tables_from_control(sf, cfg["control"]["source_group"])
    else:
        tables = cfg["tables"]
    if args.table:
        wanted = set(args.table)
        tables = [t for t in tables if t["name"] in wanted]
    if not tables:
        logger.error("no tables to load (control group empty, or --table matched nothing)")
        return 2

    # Build source/sink lazily; --dry-run needs neither a live sink nor its driver.
    watermarks = WatermarkStore(args.state)

    # --status just reports the checkpoint and exits — no lock, no connection, no load.
    if args.status:
        _print_status(tables, watermarks)
        return 0

    # --restart clears the checkpoint(s) so this run reloads from scratch.
    if args.restart:
        for t in tables:
            watermarks.reset(t["name"])
            logger.info("restart: cleared checkpoint for %s", t["name"])
    elif not args.dry_run:
        _log_resume_plan(tables, watermarks)

    try:
        with FileLock():
            if args.dry_run:
                # Dry-run still READS from the source (to report intended changes), so it
                # must connect too — it just never writes.
                source = _build_source(cfg).connect()
                try:
                    results = run(source, _NullSink(), watermarks, tables, salt, dry_run=True)
                finally:
                    source.close()
            else:
                from .deps import check_live_dependencies
                # Require only the driver the configured source actually needs.
                check_live_dependencies(cfg.get("source", {}).get("type", "sqlserver"))
                from .sink_snowflake import SnowflakeSink

                run_id = uuid.uuid4().hex[:12]
                src_label = cfg.get("source", {}).get("type", "source")
                if len(tables) > 1 and not args.no_parallel:
                    # Load tables concurrently, each with its own source + sink connection
                    # (Snowflake connections are not thread-safe). Watermarks are shared but
                    # locked, and each table writes a distinct key.
                    import concurrent.futures
                    workers = min(len(tables), args.max_workers)
                    logger.info("loading %d tables in parallel (%d workers)", len(tables), workers)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                        results = list(pool.map(
                            lambda t: _load_one(cfg, sf, t, watermarks, salt, run_id, src_label),
                            tables))
                else:
                    # Single connection for the common one-table case (avoids per-table setup).
                    source = _build_source(cfg).connect()
                    sink = SnowflakeSink(sf["connection"], sf["database"], sf["schema"]).connect()
                    try:
                        results = run(source, sink, watermarks, tables, salt, dry_run=False)
                        for r in results:
                            sink.log_transfer(run_id, src_label, r.table, r.rows_read, r.rows_written)
                    finally:
                        sink.close()
                        source.close()
    except LockHeldError as exc:
        logger.error("%s", exc)
        return 3

    total_read = sum(r.rows_read for r in results)
    total_written = sum(r.rows_written for r in results)
    logger.info("finished: %d table(s), read=%d written=%d%s",
                len(results), total_read, total_written,
                " (dry-run)" if args.dry_run else "")
    return 0


def _log_resume_plan(tables, watermarks) -> None:
    """Say, per table, whether this run resumes from a checkpoint or starts fresh."""
    for t in tables:
        cp = watermarks.checkpoint(t["name"])
        if cp and cp.get("hwm") is not None:
            note = " (last run interrupted)" if cp.get("status") == "in_progress" else ""
            logger.info("resume %s from %s=%s, %s rows already loaded%s",
                        t["name"], t["hwm_column"], cp["hwm"], cp.get("rows", 0), note)
        else:
            logger.info("fresh load: %s (no checkpoint)", t["name"])


def _print_status(tables, watermarks) -> None:
    """Print the resume checkpoint for each configured table (for `--status`)."""
    print(f"{'table':<24} {'status':<12} {'rows':>10}  {'hwm':<20} updated_at")
    print("-" * 88)
    for t in tables:
        cp = watermarks.checkpoint(t["name"]) or {}
        print(f"{t['name']:<24} {cp.get('status', 'none'):<12} {cp.get('rows', 0):>10}  "
              f"{str(cp.get('hwm', '-')):<20} {cp.get('updated_at', '-')}")


def _build_source(cfg: dict):
    src = cfg.get("source", {})
    src_type = src.get("type", "sqlserver")
    if src_type == "file":
        from .source_file import FileSource
        return FileSource(src["path"])
    if src_type == "sqlite":
        from .source_sqlite import SqliteSource
        return SqliteSource(src["path"])
    if src_type == "oracle":
        from .source_oracle import OracleSource
        return OracleSource(dsn=src.get("dsn"), user=src.get("user"),
                            password_env=src.get("password_env", "ORACLE_PASSWORD"),
                            conn_str=src.get("conn_str"))
    if src_type == "sqlserver":
        from .source_sqlserver import SqlServerSource
        return SqlServerSource(dsn=src.get("dsn"), conn_str=src.get("conn_str"))
    if src_type == "postgres":
        from .source_postgres import PostgresSource
        return PostgresSource(dsn=src.get("dsn"), host=src.get("host"),
                              port=src.get("port", 5432), dbname=src.get("dbname"),
                              user=src.get("user"),
                              password_env=src.get("password_env", "PGPASSWORD"))
    if src_type == "mysql":
        from .source_mysql import MySqlSource
        return MySqlSource(host=src.get("host"), port=src.get("port", 3306),
                           database=src.get("database"), user=src.get("user"),
                           password_env=src.get("password_env", "MYSQL_PASSWORD"))
    if src_type == "rest":
        from .source_rest import RestSource
        return RestSource(base_url=src["base_url"], token_env=src.get("token_env"),
                          records_key=src.get("records_key"),
                          since_param=src.get("since_param"),
                          timeout=src.get("timeout", 30))
    if src_type == "excel":
        from .source_excel import ExcelSource
        return ExcelSource(src["path"])
    if src_type == "parquet":
        from .source_parquet import ParquetSource
        return ParquetSource(src["path"])
    raise ValueError(f"unknown source.type: {src_type!r}")


class _NullSink:
    """Dry-run sink: never connects, never writes."""

    def write(self, table, rows):
        return 0

    def close(self):
        pass


if __name__ == "__main__":
    sys.exit(main())
