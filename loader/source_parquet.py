"""Parquet source — a columnar data-lake file as a relational table. pyarrow imported lazily.

The file is sorted by the high-water-mark and filtered with Arrow compute, then yielded in
batch_size slices — so incremental checkpointing stays correct even if the file isn't pre-sorted.
Same fetch_batches / count contract as the other sources ('table' is informational here).

Bounded-memory by design: a global sort for safe checkpointing means the file is read whole
(as a compact Arrow table), so this suits data-lake extract files, not unbounded streams — the
DB sources cover those with server-side cursors.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ParquetSource:
    def __init__(self, path: str):
        self.path = Path(path)

    def connect(self):
        if not self.path.exists():
            raise FileNotFoundError(f"parquet source not found: {self.path}")
        logger.info("parquet source: %s", self.path)
        return self

    def fetch_batches(self, table: str, hwm_column: str, since, batch_size: int):
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        tbl = pq.read_table(self.path)
        if hwm_column not in tbl.column_names:
            raise ValueError(f"hwm_column {hwm_column!r} not in {self.path.name} columns")
        tbl = tbl.sort_by([(hwm_column, "ascending")])
        if since is not None:
            tbl = tbl.filter(pc.greater(tbl[hwm_column], since))
        for i in range(0, tbl.num_rows, batch_size):
            rows = tbl.slice(i, batch_size).to_pylist()
            if rows:
                yield rows

    def count(self, table: str, hwm_column: str, since) -> int:
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        tbl = pq.read_table(self.path, columns=[hwm_column])
        if since is None:
            return tbl.num_rows
        return pc.sum(pc.cast(pc.greater(tbl[hwm_column], since), "int64")).as_py() or 0

    def close(self):
        pass
