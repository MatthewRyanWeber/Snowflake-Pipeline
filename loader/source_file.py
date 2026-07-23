"""File source — reads a CSV as a stand-in relational table.

Lets the loader run end-to-end offline (dry-run, tests) against the synthetic patients.csv
before a real SQL Server is available. Same fetch_batches contract as SqlServerSource, so
switching sources is a config change, not a code change.
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileSource:
    def __init__(self, path: str):
        self.path = Path(path)

    def connect(self):
        if not self.path.exists():
            raise FileNotFoundError(f"file source not found: {self.path}")
        logger.info("file source: %s", self.path)
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        with self.path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            return  # empty file -> no batches (not an error)
        if hwm_column not in rows[0].keys():
            raise ValueError(f"hwm_column {hwm_column!r} not in {self.path.name} columns")

        # Incremental filter + ordering, mirroring the SQL 'WHERE hwm > since ORDER BY hwm'.
        rows.sort(key=lambda r: r[hwm_column])
        if since is not None:
            rows = [r for r in rows if str(r[hwm_column]) > str(since)]

        for i in range(0, len(rows), batch_size):
            yield rows[i:i + batch_size]

    def count(self, table: str, hwm_column: str, since) -> int:
        with self.path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            return 0
        if since is None:
            return len(rows)
        return sum(1 for r in rows if str(r[hwm_column]) > str(since))

    def close(self):
        pass
