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
        # Fast path: write_pandas stages the batch as parquet and COPYs it — far faster than
        # row-by-row INSERT (which caps out near a few hundred rows/s on a wide table).
        # Check BOTH deps up front (pandas import succeeding but pyarrow missing would fail
        # inside write_pandas, past an import-only guard).
        try:
            import pandas  # noqa: F401
            import pyarrow  # noqa: F401
        except ImportError:
            return self._write_insert(table, rows)
        return self._write_pandas(table, rows)

    def _write_pandas(self, table: str, rows: list[dict]) -> int:
        import pandas as pd
        from snowflake.connector.pandas_tools import write_pandas

        df = pd.DataFrame(rows)
        df.columns = [c.upper() for c in df.columns]  # match Snowflake's unquoted identifiers
        _, _, nrows, _ = write_pandas(
            self._conn, df, table_name=table.upper(),
            database=self.database, schema=self.schema, quote_identifiers=False,
        )
        logger.debug("write_pandas %d rows -> %s.%s", nrows, self.schema, table)
        return nrows

    def _write_insert(self, table: str, rows: list[dict]) -> int:
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
        logger.debug("insert %d rows -> %s.%s", len(rows), self.schema, table)
        return len(rows)

    def log_transfer(self, run_id, source, target, rows_read, rows_written) -> None:
        """Record one transfer in the native audit table GOV.LOAD_LOG (best-effort)."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                f"INSERT INTO {self.database}.GOV.LOAD_LOG "
                "(run_id, source, target, rows_read, rows_written, loaded_by) "
                "SELECT %s, %s, %s, %s, %s, CURRENT_USER()",
                (run_id, source, target, rows_read, rows_written),
            )
            cur.close()
        except Exception as exc:  # noqa: BLE001 - logging must never fail the load
            logger.warning("could not write transfer log: %s", exc)

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
