"""Dependency gate. Runs before any live load — aborts if a required package is missing.

Pure-logic paths (masking, watermark, tests) don't import this, so they work with only
the stdlib + pyyaml. The heavy drivers are checked here, at the point they're actually used.
"""

import importlib
import logging

logger = logging.getLogger(__name__)

# Always needed for a live load, regardless of source. (import_name, pip_name, why)
BASE_REQUIREMENTS = [
    ("yaml", "pyyaml", "read config/loader.yaml"),
    ("snowflake.connector", "snowflake-connector-python", "load rows into Snowflake RAW"),
]

# The driver each source.type needs. file/sqlite are stdlib-only (absent here => no extra dep).
SOURCE_DRIVERS = {
    "sqlserver": ("pyodbc", "pyodbc", "extract from SQL Server (ODBC)"),
    "oracle": ("oracledb", "oracledb", "extract from Oracle"),
    "postgres": ("psycopg2", "psycopg2-binary", "extract from PostgreSQL"),
    "mysql": ("pymysql", "pymysql", "extract from MySQL/MariaDB"),
    "rest": ("requests", "requests", "extract from a REST API"),
    "excel": ("openpyxl", "openpyxl", "read .xlsx source files"),
    "parquet": ("pyarrow", "pyarrow", "read Parquet source files"),
}


class MissingDependencyError(RuntimeError):
    pass


def check_live_dependencies(source_type: str = "sqlserver") -> None:
    """Abort with a clear, actionable error if a live-run dependency is missing.

    Only the driver for the configured source.type is required (plus the base packages).
    We do NOT silently skip a driver — that would let a load appear to succeed while
    doing nothing. Fail loud instead (project + global rule).
    """
    requirements = list(BASE_REQUIREMENTS)
    driver = SOURCE_DRIVERS.get(source_type)
    if driver:
        requirements.append(driver)

    missing = []
    for import_name, pip_name, why in requirements:
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
