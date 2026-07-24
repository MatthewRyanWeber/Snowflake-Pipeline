"""Shared base for the relational sources.

Every SQL source runs the same query and the same batched, incremental fetch loop — only the
driver, the parameter placeholder, the streaming-cursor flavour, and the row shape differ. This
base owns the common 90%; each concrete source overrides just the driver-specific hooks:

  _open()          -> a live DBAPI connection (the only required override)
  PLACEHOLDER      -> the bind marker for the WHERE clause ('?', '%s', ':since')
  _stream_cursor() -> a cursor that streams rows server-side (default: a plain cursor)
  _execute()       -> how a value binds to the placeholder (default: positional tuple)
  _adapt()         -> fetched rows -> list[dict] (default: zip column names with row tuples)

fetch_batches yields rows ORDER BY hwm ASC in batch_size chunks; the caller checkpoints after
each committed batch, so ordering is what makes a crash resume safely from the last batch.
"""

import logging

logger = logging.getLogger(__name__)


class SqlSource:
    PLACEHOLDER = "?"
    LABEL = "SQL"

    def _open(self):
        raise NotImplementedError

    def connect(self):
        self._conn = self._open()
        logger.info("connected to %s source", self.LABEL)
        return self

    # --- driver-specific hooks (sensible defaults; override as needed) ---

    def _stream_cursor(self):
        """A cursor for the streaming SELECT. Override for server-side/unbuffered cursors."""
        return self._conn.cursor()

    def _execute(self, cur, sql: str, since) -> None:
        if since is None:
            cur.execute(sql)
        else:
            cur.execute(sql, (since,))

    def _adapt(self, cur, rows) -> list:
        columns = [c[0] for c in cur.description]
        return [dict(zip(columns, r)) for r in rows]

    # --- shared contract ---

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        cur = self._stream_cursor()
        if since is None:
            sql = f"SELECT * FROM {table} ORDER BY {hwm_column} ASC"
        else:
            sql = (f"SELECT * FROM {table} WHERE {hwm_column} > {self.PLACEHOLDER} "
                   f"ORDER BY {hwm_column} ASC")
        self._execute(cur, sql, since)
        try:
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield self._adapt(cur, rows)
        finally:
            cur.close()  # closes even on early break / exception mid-stream

    def count(self, table: str, hwm_column: str, since) -> int:
        cur = self._conn.cursor()  # plain cursor: a scalar, never the streaming variant
        try:
            if since is None:
                sql = f"SELECT COUNT(*) FROM {table}"
            else:
                sql = f"SELECT COUNT(*) FROM {table} WHERE {hwm_column} > {self.PLACEHOLDER}"
            self._execute(cur, sql, since)  # same bind style as fetch (named binds, etc.)
            return cur.fetchone()[0]
        finally:
            cur.close()

    def close(self):
        if getattr(self, "_conn", None) is not None:
            self._conn.close()
            self._conn = None
