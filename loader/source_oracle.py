"""Oracle source. `oracledb` (thin mode — no Oracle client install) imported lazily.

Same fetch_batches / count contract as the other sources, so Oracle is a config change
(source.type: oracle), not a code change. Password comes from an environment variable named
in config (default ORACLE_PASSWORD) — never inline a secret in the YAML.
"""

import logging
import os

logger = logging.getLogger(__name__)


class OracleSource:
    def __init__(self, dsn=None, user=None, password_env="ORACLE_PASSWORD", conn_str=None):
        # dsn is "host:port/service_name". conn_str, if given, is a full oracledb connect string.
        self.dsn = dsn
        self.user = user
        self.password_env = password_env
        self.conn_str = conn_str
        self._conn = None

    def connect(self):
        import oracledb  # lazy: only needed for a live Oracle run

        if self.conn_str:
            self._conn = oracledb.connect(self.conn_str)
        else:
            password = os.environ.get(self.password_env)
            if not self.user or password is None:
                raise ValueError(
                    f"OracleSource needs user + ${self.password_env} (password via env, not config)"
                )
            self._conn = oracledb.connect(user=self.user, password=password, dsn=self.dsn)
        logger.info("connected to Oracle source")
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        cur = self._conn.cursor()
        if since is None:
            cur.execute(f"SELECT * FROM {table} ORDER BY {hwm_column} ASC")
        else:
            cur.execute(
                f"SELECT * FROM {table} WHERE {hwm_column} > :since ORDER BY {hwm_column} ASC",
                since=since,
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
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {hwm_column} > :since", since=since)
        return cur.fetchone()[0]

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
