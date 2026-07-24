"""PostgreSQL source. psycopg2 imported lazily; the batched, incremental fetch lives in
SqlSource. Moving a table to Postgres is a source.type change, not code.

Password comes from an environment variable named in config (default PGPASSWORD) — never inline
a secret. A named (server-side) cursor streams rows so memory stays flat on big tables.
"""

import os

from .source_sql import SqlSource


class PostgresSource(SqlSource):
    PLACEHOLDER = "%s"
    LABEL = "PostgreSQL"

    def __init__(self, dsn=None, host=None, port=5432, dbname=None, user=None,
                 password_env="PGPASSWORD"):
        self.dsn = dsn
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password_env = password_env
        self._conn = None

    def _open(self):
        import psycopg2  # lazy: only needed for a live Postgres run

        if self.dsn:
            return psycopg2.connect(self.dsn)
        password = os.environ.get(self.password_env)
        return psycopg2.connect(host=self.host, port=self.port, dbname=self.dbname,
                                user=self.user, password=password)

    def _stream_cursor(self):
        # Named cursor => server-side: rows stream in chunks, never the whole result at once.
        return self._conn.cursor(name="loader_stream")
