"""Dependency gate. Runs before any live load — aborts if a required package is missing.

Pure-logic paths (masking, watermark, tests) don't import this, so they work with only
the stdlib + pyyaml. The heavy drivers are checked here, at the point they're actually used.
"""

import importlib
import logging

logger = logging.getLogger(__name__)

# (import_name, pip_name, why)
LIVE_REQUIREMENTS = [
    ("yaml", "pyyaml", "read config/loader.yaml"),
    ("snowflake.connector", "snowflake-connector-python", "load rows into Snowflake RAW"),
    ("pyodbc", "pyodbc", "extract from SQL Server (ODBC)"),
]


class MissingDependencyError(RuntimeError):
    pass


def check_live_dependencies(require_source: bool = True) -> None:
    """Abort with a clear, actionable error if a live-run dependency is missing.

    We do NOT silently skip a driver — that would let a load appear to succeed while
    doing nothing. Fail loud instead (project + global rule).
    """
    missing = []
    for import_name, pip_name, why in LIVE_REQUIREMENTS:
        if not require_source and import_name == "pyodbc":
            continue
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append((pip_name, why))

    if missing:
        lines = [f"  - {pip} ({why})" for pip, why in missing]
        raise MissingDependencyError(
            "Missing required packages for a live load:\n"
            + "\n".join(lines)
            + "\n\nInstall them:  pip install -r requirements.txt"
        )
    logger.debug("all live dependencies present")
