"""SQL Server source. pyodbc is imported lazily so this module imports without a driver.

Only the connection is driver-specific; the batched, incremental fetch lives in SqlSource.
Connection details come from a DSN or a full ODBC connection string supplied via env/config —
never hardcoded here, so the password stays out of the repo.
"""

from .source_sql import SqlSource


class SqlServerSource(SqlSource):
    PLACEHOLDER = "?"
    LABEL = "SQL Server"

    def __init__(self, dsn: str | None = None, conn_str: str | None = None):
        self.dsn = dsn
        self.conn_str = conn_str
        self._conn = None

    def _open(self):
        import pyodbc  # lazy: only needed for a live run

        if self.conn_str:
            return pyodbc.connect(self.conn_str)
        if self.dsn:
            return pyodbc.connect(f"DSN={self.dsn}")
        raise ValueError("SqlServerSource needs a dsn or conn_str")
