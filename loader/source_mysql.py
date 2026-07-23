"""MySQL / MariaDB source. PyMySQL imported lazily; same contract as the other relational
sources, so moving a table to MySQL is a source.type change, not code.

Password comes from an environment variable named in config (default MYSQL_PASSWORD) — never
inline a secret. An unbuffered (SS) cursor streams rows so memory stays flat on big tables.
"""

import logging
import os

logger = logging.getLogger(__name__)


class MySqlSource:
    def __init__(self, host=None, port=3306, database=None, user=None,
                 password_env="MYSQL_PASSWORD"):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password_env = password_env
        self._conn = None

    def connect(self):
        import pymysql  # lazy: only needed for a live MySQL run

        password = os.environ.get(self.password_env)
        self._conn = pymysql.connect(host=self.host, port=self.port, user=self.user,
                                     password=password, database=self.database)
        logger.info("connected to MySQL source")
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        from pymysql.cursors import SSDictCursor  # unbuffered: stream, don't buffer all rows

        cur = self._conn.cursor(SSDictCursor)
        if since is None:
            cur.execute(f"SELECT * FROM {table} ORDER BY {hwm_column} ASC")
        else:
            cur.execute(
                f"SELECT * FROM {table} WHERE {hwm_column} > %s ORDER BY {hwm_column} ASC",
                (since,),
            )
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield list(rows)
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
