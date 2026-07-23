"""PostgreSQL source. psycopg2 imported lazily; same fetch_batches / count contract as the
other relational sources, so moving a table to Postgres is a source.type change, not code.

Password comes from an environment variable named in config (default PGPASSWORD) — never inline
a secret in the YAML. A named (server-side) cursor streams rows so memory stays flat on big tables.
"""

import logging
import os

logger = logging.getLogger(__name__)


class PostgresSource:
    def __init__(self, dsn=None, host=None, port=5432, dbname=None, user=None,
                 password_env="PGPASSWORD"):
        self.dsn = dsn
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password_env = password_env
        self._conn = None

    def connect(self):
        import psycopg2  # lazy: only needed for a live Postgres run

        if self.dsn:
            self._conn = psycopg2.connect(self.dsn)
        else:
            password = os.environ.get(self.password_env)
            self._conn = psycopg2.connect(host=self.host, port=self.port, dbname=self.dbname,
                                          user=self.user, password=password)
        logger.info("connected to PostgreSQL source")
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        # Named cursor => server-side: rows stream in batch_size chunks, never all at once.
        cur = self._conn.cursor(name="loader_stream")
        cur.itersize = batch_size
        if since is None:
            cur.execute(f"SELECT * FROM {table} ORDER BY {hwm_column} ASC")
        else:
            cur.execute(
                f"SELECT * FROM {table} WHERE {hwm_column} > %s ORDER BY {hwm_column} ASC",
                (since,),
            )
        # A named (server-side) cursor only populates .description after the first fetch.
        columns = None
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            if columns is None:
                columns = [c[0] for c in cur.description]
            yield [dict(zip(columns, r)) for r in rows]
        cur.close()

    def count(self, table: str, hwm_column: str, since) -> int:
        cur = self._conn.cursor()
        if since is None:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
        else:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {hwm_column} > %s", (since,))
        return cur.fetchone()[0]

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
