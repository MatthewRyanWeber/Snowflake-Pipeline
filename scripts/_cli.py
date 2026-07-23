"""Shared CLI conventions for the connector-based scripts.

One definition of the common flags (--connection / --database / --config / --verbose), one
way to open a Snowflake connection, and one source of truth for the connection name
(config/pipeline.conf -> SF_CONNECTION). Every script speaks the same language so a flag you
learn on one works on the rest.
"""

import argparse
import logging
from pathlib import Path

DEFAULT_DATABASE = "HEALTH_ANALYTICS"
DEFAULT_CONFIG = Path("config/pipeline.conf")
DEFAULT_CONNECTION = "snowflake_pipeline"


def read_connection_name(config_path=DEFAULT_CONFIG, override=None) -> str:
    """--connection wins; else SF_CONNECTION from config/pipeline.conf; else the default."""
    if override:
        return override
    path = Path(config_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SF_CONNECTION") and "=" in line:
                return line.split("=", 1)[1].strip()
    return DEFAULT_CONNECTION


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--connection", help="connection name (default: SF_CONNECTION in the config)")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--verbose", action="store_true")
    return parser


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


def connect(args):
    """Open a Snowflake connection from the common args."""
    import snowflake.connector as sc
    name = read_connection_name(getattr(args, "config", DEFAULT_CONFIG),
                                getattr(args, "connection", None))
    return sc.connect(connection_name=name, database=getattr(args, "database", DEFAULT_DATABASE))
