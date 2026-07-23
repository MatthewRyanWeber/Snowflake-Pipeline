"""Loader orchestration: extract -> mask -> load, per table, incremental + checkpointed.

Source and sink are injected so the whole flow is unit-testable with fakes (no live DB).
Each committed batch advances the persisted high-water-mark, so a crash resumes cleanly.
"""

import logging
import re

from .masking import mask_row
from .watermark import WatermarkStore

logger = logging.getLogger(__name__)

# Table/column names are interpolated into SQL (identifiers can't be bound parameters),
# so constrain them to a safe shape to prevent injection via a hostile config file.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$.]*$")


def _check_identifier(kind: str, value) -> str:
    if not isinstance(value, str) or not _IDENT_RE.match(value):
        raise ValueError(f"unsafe {kind} identifier in config: {value!r}")
    return value


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
    name = _check_identifier("table name", table_cfg["name"])
    target = _check_identifier("target", table_cfg.get("target", name))
    hwm_column = _check_identifier("hwm_column", table_cfg["hwm_column"])
    batch_size = int(table_cfg.get("batch_size", 5000))
    column_policies = table_cfg.get("mask", {}) or {}

    result = LoadResult(target)
    result.dry_run = dry_run
    since = watermarks.get(name)
    logger.info("load %s -> %s (hwm_column=%s, since=%s, dry_run=%s)",
                name, target, hwm_column, since, dry_run)

    last_hwm = since
    for batch in source.fetch_batches(name, hwm_column, since, batch_size):
        if not batch:
            continue
        result.batches += 1
        result.rows_read += len(batch)
        masked = [mask_row(r, column_policies, salt) for r in batch]

        if dry_run:
            if result.batches == 1:
                logger.info("[dry-run] sample masked row: %s", masked[0])
            logger.info("[dry-run] would write %d rows to %s (batch %d)",
                        len(masked), target, result.batches)
        else:
            written = sink.write(target, masked)
            result.rows_written += written

        # Rows are fetched ORDER BY hwm ASC, so the LAST row of the batch carries the
        # batch's max HWM. Take it as-is (native type) — never compare stored-vs-native
        # values client-side, which broke for numeric/timestamp keys. Checkpoint only
        # after the commit above (crash-safe: a crash resumes from the last flushed hwm).
        batch_hwm = batch[-1].get(hwm_column)
        if batch_hwm is not None:
            last_hwm = batch_hwm
            if not dry_run:
                watermarks.set(name, last_hwm)

    result.new_watermark = last_hwm
    logger.info("done %s: %r", target, result)
    return result


def run(source, sink, watermarks: WatermarkStore, tables: list[dict],
        salt: str, dry_run: bool = False) -> list[LoadResult]:
    results = []
    for table_cfg in tables:
        results.append(load_table(source, sink, watermarks, table_cfg, salt, dry_run))
    return results
