"""MySQL / MariaDB source. PyMySQL imported lazily; the batched, incremental fetch lives in
SqlSource. Moving a table to MySQL is a source.type change, not code.

Password comes from an environment variable named in config (default MYSQL_PASSWORD) — never
inline a secret. An unbuffered (SS) cursor streams rows so memory stays flat on big tables.
"""

import os

from .source_sql import SqlSource


class MySqlSource(SqlSource):
    PLACEHOLDER = "%s"
    LABEL = "MySQL"

    def __init__(self, host=None, port=3306, database=None, user=None,
                 password_env="MYSQL_PASSWORD"):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password_env = password_env
        self._conn = None

    def _open(self):
        import pymysql  # lazy: only needed for a live MySQL run

        password = os.environ.get(self.password_env)
        return pymysql.connect(host=self.host, port=self.port, user=self.user,
                               password=password, database=self.database)

    def _stream_cursor(self):
        from pymysql.cursors import SSDictCursor  # unbuffered: stream, don't buffer all rows

        return self._conn.cursor(SSDictCursor)

    def _adapt(self, cur, rows) -> list:
        return list(rows)  # SSDictCursor already yields dict rows
