"""REST API source — paginated JSON over HTTP. requests imported lazily.

The 'table' is a resource path appended to base_url; rows come back as a JSON array (or nested
under records_key). Pagination is limit/offset; incremental loads pass the high-water-mark as a
'<hwm>_gt' filter (override with since_param). A bearer token is read from an env var, not config.

Same fetch_batches / count contract as the DB sources, so an API is a source.type change, not code.
"""

import logging
import os

logger = logging.getLogger(__name__)


class RestSource:
    def __init__(self, base_url: str, token_env=None, records_key=None,
                 since_param=None, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.token_env = token_env
        self.records_key = records_key
        self.since_param = since_param
        self.timeout = timeout

    def connect(self):
        logger.info("REST source: %s", self.base_url)
        return self

    def _headers(self):
        if self.token_env:
            token = os.environ.get(self.token_env)
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}

    def _params(self, hwm_column, since, limit, offset):
        params = {"limit": limit, "offset": offset}
        if since is not None:
            params[self.since_param or f"{hwm_column}_gt"] = since
        return params

    def _records(self, payload):
        return payload[self.records_key] if self.records_key else payload

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        import requests

        url = f"{self.base_url}/{table}"
        offset = 0
        while True:
            resp = requests.get(url, params=self._params(hwm_column, since, batch_size, offset),
                                headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            rows = self._records(resp.json())
            if not rows:
                break
            yield rows
            if len(rows) < batch_size:  # short page => last page
                break
            offset += batch_size

    def count(self, table: str, hwm_column: str, since):
        # Contract: count() returns an int, or None when a source cannot cheaply determine a
        # total. Here: read an X-Total-Count header if the API sets one, else None (the progress
        # bar drops to count-only). Never fabricate a total.
        import requests

        resp = requests.get(f"{self.base_url}/{table}",
                            params=self._params(hwm_column, since, 1, 0),
                            headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        total = resp.headers.get("X-Total-Count")
        return int(total) if total is not None else None

    def close(self):
        pass
