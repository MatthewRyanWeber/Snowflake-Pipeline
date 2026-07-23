"""Snowflake sink. snowflake-connector-python is imported lazily.

Idempotent-friendly: writes go to RAW via parameterized executemany. The high-water-mark
(source side) is what prevents duplicates across re-runs, so writes stay simple INSERTs.
"""

import logging

logger = logging.getLogger(__name__)


class SnowflakeSink:
    def __init__(self, connection_name: str, database: str, schema: str):
        # ASSUMPTION: auth comes from the named connection in ~/.snowsql/config (or the
        # connections.toml the connector reads) — no credentials passed here.
        self.connection_name = connection_name
        self.database = database
        self.schema = schema
        self._conn = None

    def connect(self):
        import snowflake.connector  # lazy: only needed for a live run
        from snowflake.connector import errors as sferrors

        from .retry import with_retry

        def _open():
            return snowflake.connector.connect(
                connection_name=self.connection_name,
                database=self.database,
                schema=self.schema,
                login_timeout=15,      # fail fast on an unreachable account
                network_timeout=30,    # bound each request, don't hang a run
            )

        # Retry only transient connectivity errors; a bad credential fails immediately.
        self._conn = with_retry(
            _open, what="Snowflake connect",
            exceptions=(sferrors.OperationalError, sferrors.InterfaceError),
        )
        logger.info("connected to Snowflake %s.%s", self.database, self.schema)
        return self

    def write(self, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        columns = list(rows[0].keys())
        placeholders = ", ".join(["%s"] * len(columns))
        collist = ", ".join(columns)
        sql = f"INSERT INTO {self.schema}.{table} ({collist}) VALUES ({placeholders})"
        params = [tuple(r.get(c) for c in columns) for r in rows]
        cur = self._conn.cursor()
        try:
            cur.executemany(sql, params)
            self._conn.commit()
        finally:
            cur.close()
        logger.debug("wrote %d rows -> %s.%s", len(rows), self.schema, table)
        return len(rows)

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
