"""Oracle source. `oracledb` (thin mode, no Oracle client install) imported lazily.

Only the connection and Oracle's named-bind style (`:since`) are driver-specific; the batched,
incremental fetch lives in SqlSource. Password comes from an environment variable named in
config (default ORACLE_PASSWORD) — never inline a secret in the YAML.
"""

import os

from .source_sql import SqlSource


class OracleSource(SqlSource):
    PLACEHOLDER = ":since"
    LABEL = "Oracle"

    def __init__(self, dsn=None, user=None, password_env="ORACLE_PASSWORD", conn_str=None):
        # dsn is "host:port/service_name". conn_str, if given, is a full oracledb connect string.
        self.dsn = dsn
        self.user = user
        self.password_env = password_env
        self.conn_str = conn_str
        self._conn = None

    def _open(self):
        import oracledb  # lazy: only needed for a live Oracle run

        if self.conn_str:
            return oracledb.connect(self.conn_str)
        password = os.environ.get(self.password_env)
        if not self.user or password is None:
            raise ValueError(
                f"OracleSource needs user + ${self.password_env} (password via env, not config)")
        return oracledb.connect(user=self.user, password=password, dsn=self.dsn)

    def _execute(self, cur, sql: str, since) -> None:
        if since is None:
            cur.execute(sql)
        else:
            cur.execute(sql, since=since)  # Oracle binds :since by name
