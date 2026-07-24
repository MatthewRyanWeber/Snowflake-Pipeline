"""SQLite source — a real relational DB engine, stdlib only (no driver install).

Proves the loader's relational path end-to-end (DB -> mask -> Snowflake) against an actual
database, not just a CSV. All the query/fetch logic lives in SqlSource; this only opens the
connection. Switching to SQL Server in production is a source.type change, not a code change.
"""

import sqlite3
from pathlib import Path

from .source_sql import SqlSource


class SqliteSource(SqlSource):
    PLACEHOLDER = "?"
    LABEL = "sqlite"

    def __init__(self, path: str):
        self.path = Path(path)
        self._conn = None

    def _open(self):
        if not self.path.exists():
            raise FileNotFoundError(f"sqlite db not found: {self.path}")
        return sqlite3.connect(str(self.path))
