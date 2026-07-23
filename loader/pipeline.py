"""Loader orchestration: extract -> mask -> load, per table, incremental + checkpointed.

Source and sink are injected so the whole flow is unit-testable with fakes (no live DB).
Each committed batch advances the persisted high-water-mark, so a crash resumes cleanly.
"""

import logging

from .masking import mask_row
from .watermark import WatermarkStore

logger = logging.getLogger(__name__)


class LoadResult:
    def __init__(self, table: str):
        self.table = table
        self.rows_read = 0
        self.rows_written = 0
        self.batches = 0
        self.new_watermark = None
        self.dry_run = False

    def __repr__(self):
        mode = "DRY-RUN " if self.dry_run else ""
        return (f"<{mode}{self.table}: read={self.rows_read} written={self.rows_written} "
                f"batches={self.batches} hwm={self.new_watermark}>")


def load_table(source, sink, watermarks: WatermarkStore, table_cfg: dict,
               salt: str, dry_run: bool = False) -> LoadResult:
    """Load one configured table incrementally.

    table_cfg keys: name, target (RAW table), hwm_column, batch_size, mask (col->policy).
    """
    name = table_cfg["name"]
    target = table_cfg.get("target", name)
    hwm_column = table_cfg["hwm_column"]
    batch_size = int(table_cfg.get("batch_size", 5000))
    column_policies = table_cfg.get("mask", {}) or {}

    result = LoadResult(target)
    result.dry_run = dry_run
    since = watermarks.get(name)
    logger.info("load %s -> %s (hwm_column=%s, since=%s, dry_run=%s)",
                name, target, hwm_column, since, dry_run)

    max_seen = since
    for batch in source.fetch_batches(name, hwm_column, since, batch_size):
        result.batches += 1
        result.rows_read += len(batch)
        masked = [mask_row(r, column_policies, salt) for r in batch]

        # Track the batch's max HWM to checkpoint after a successful commit.
        batch_max = max((r.get(hwm_column) for r in batch if r.get(hwm_column) is not None),
                        default=max_seen)

        if dry_run:
            # No writes. Report what would happen; leave the watermark untouched.
            if result.batches == 1 and masked:
                logger.info("[dry-run] sample masked row: %s", masked[0])
            logger.info("[dry-run] would write %d rows to %s (batch %d)",
                        len(masked), target, result.batches)
        else:
            written = sink.write(target, masked)
            result.rows_written += written
            # Checkpoint only after the commit — order matters for crash-safety.
            if batch_max is not None:
                watermarks.set(name, batch_max)
        max_seen = _max(max_seen, batch_max)

    result.new_watermark = max_seen
    logger.info("done %s: %r", target, result)
    return result


def _max(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b


def run(source, sink, watermarks: WatermarkStore, tables: list[dict],
        salt: str, dry_run: bool = False) -> list[LoadResult]:
    results = []
    for table_cfg in tables:
        results.append(load_table(source, sink, watermarks, table_cfg, salt, dry_run))
    return results
