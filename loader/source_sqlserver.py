"""SQL Server extractor. pyodbc is imported lazily so this module imports without a driver.

Yields rows in batches, filtered by a high-water-mark column for incremental loads.
"""

import logging

logger = logging.getLogger(__name__)


class SqlServerSource:
    def __init__(self, dsn: str | None = None, conn_str: str | None = None):
        # ASSUMPTION: connection details come from a DSN or a full ODBC connection string
        # supplied via env/config — never hardcoded here. Password stays out of the repo.
        self.dsn = dsn
        self.conn_str = conn_str
        self._conn = None

    def connect(self):
        import pyodbc  # lazy: only needed for a live run

        if self.conn_str:
            self._conn = pyodbc.connect(self.conn_str)
        elif self.dsn:
            self._conn = pyodbc.connect(f"DSN={self.dsn}")
        else:
            raise ValueError("SqlServerSource needs a dsn or conn_str")
        logger.info("connected to SQL Server source")
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        """Yield lists of dict rows where hwm_column > since, ordered by hwm_column.

        Ordering by the HWM column is what makes checkpointing safe: a batch commit means
        every row up to that batch's max HWM is durably loaded.
        """
        cur = self._conn.cursor()
        if since is None:
            cur.execute(f"SELECT * FROM {table} ORDER BY {hwm_column} ASC")
        else:
            cur.execute(
                f"SELECT * FROM {table} WHERE {hwm_column} > ? ORDER BY {hwm_column} ASC",
                since,
            )
        columns = [c[0] for c in cur.description]
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield [dict(zip(columns, r)) for r in rows]

    def count(self, table: str, hwm_column: str, since) -> int:
        cur = self._conn.cursor()
        if since is None:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {hwm_column} > ?", since)
        return cur.fetchone()[0]

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
