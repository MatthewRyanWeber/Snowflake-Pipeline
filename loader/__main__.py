"""CLI entrypoint:  python -m loader [--dry-run] [--config PATH] [--table NAME] [--verbose]

--dry-run reports intended row counts + a masked sample without writing anything.
A real run is incremental (high-water-mark) and safe to re-run without duplicates.
"""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .lock import FileLock, LockHeldError
from .logging_config import configure
from .masking import DEFAULT_SALT
from .pipeline import run
from .watermark import WatermarkStore

logger = logging.getLogger("loader")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="loader", description="SQL Server -> Snowflake RAW loader")
    p.add_argument("--config", type=Path, default=Path("config/loader.yaml"))
    p.add_argument("--dry-run", action="store_true", help="report intended changes, write nothing")
    p.add_argument("--table", action="append", help="limit to named table(s); repeatable")
    p.add_argument("--state", type=Path, default=Path("state/watermarks.json"))
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"loader {__version__}")
    args = p.parse_args(argv)

    configure(verbose=args.verbose)
    cfg = load_config(args.config)

    tables = cfg["tables"]
    if args.table:
        wanted = set(args.table)
        tables = [t for t in tables if t["name"] in wanted]
        if not tables:
            logger.error("no configured tables match --table %s", args.table)
            return 2

    salt = cfg.get("masking", {}).get("salt", DEFAULT_SALT)
    sf = cfg["snowflake"]

    # Build source/sink lazily; --dry-run needs neither a live sink nor its driver.
    watermarks = WatermarkStore(args.state)

    try:
        with FileLock():
            if args.dry_run:
                source = _build_source(cfg)
                results = run(source, _NullSink(), watermarks, tables, salt, dry_run=True)
            else:
                from .deps import check_live_dependencies
                check_live_dependencies(require_source=True)
                from .sink_snowflake import SnowflakeSink

                source = _build_source(cfg)
                source.connect()
                sink = SnowflakeSink(sf["connection"], sf["database"], sf["schema"]).connect()
                try:
                    results = run(source, sink, watermarks, tables, salt, dry_run=False)
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


def _build_source(cfg: dict):
    src = cfg.get("source", {})
    src_type = src.get("type", "sqlserver")
    if src_type == "file":
        from .source_file import FileSource
        return FileSource(src["path"])
    if src_type == "sqlserver":
        from .source_sqlserver import SqlServerSource
        return SqlServerSource(dsn=src.get("dsn"), conn_str=src.get("conn_str"))
    raise ValueError(f"unknown source.type: {src_type!r}")


class _NullSink:
    """Dry-run sink: never connects, never writes."""

    def write(self, table, rows):
        return 0

    def close(self):
        pass


if __name__ == "__main__":
    sys.exit(main())
