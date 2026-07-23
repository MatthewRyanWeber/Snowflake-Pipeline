"""SQLite source — a real relational DB engine, stdlib only (no driver install).

Proves the loader's relational path end-to-end (DB → mask → Snowflake) against an actual
database, not just a CSV. Same fetch_batches contract as SqlServerSource, so switching to
SQL Server in production is a config change (source.type), not a code change.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class SqliteSource:
    def __init__(self, path: str):
        self.path = Path(path)
        self._conn = None

    def connect(self):
        if not self.path.exists():
            raise FileNotFoundError(f"sqlite db not found: {self.path}")
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        logger.info("connected to sqlite source: %s", self.path)
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        cur = self._conn.cursor()
        if since is None:
            cur.execute(f"SELECT * FROM {table} ORDER BY {hwm_column} ASC")
        else:
            cur.execute(
                f"SELECT * FROM {table} WHERE {hwm_column} > ? ORDER BY {hwm_column} ASC",
                (since,),
            )
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield [dict(r) for r in rows]

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
