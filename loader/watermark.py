"""Checkpoint store — persisted, resumable load state per table.

After every committed batch the loader records that table's checkpoint: the high-water-mark
reached (the resume cursor), how many rows have been loaded, and a status. A crash mid-load
resumes from the last checkpoint, never reloading committed rows and never skipping uncommitted
ones. `--restart` clears a table's checkpoint to force a full reload; `--status` reports it.

On-disk format (JSON, one entry per table):
    { "patients": { "hwm": 12345, "rows": 8000, "status": "in_progress", "updated_at": "..." } }
A file written by an older build (a bare scalar per table) is still read as its `hwm`, so an
in-flight load keeps resuming across an upgrade.
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class WatermarkStore:
    def __init__(self, path: Path = Path("state/watermarks.json")):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        self._lock = threading.Lock()   # parallel table loads share one store
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            # Corrupt state must not silently reset to a full reload — fail loud.
            raise RuntimeError(f"unreadable checkpoint state {self.path}: {exc}") from exc
        # Upgrade a legacy {table: scalar} file to the record form on read.
        self._data = {
            table: (rec if isinstance(rec, dict) else {"hwm": rec})
            for table, rec in raw.items()
        }

    # --- reads ---

    def get(self, table: str):
        """The resume cursor (high-water-mark) for a table, or None for a fresh load."""
        rec = self._data.get(table)
        return rec.get("hwm") if rec else None

    def checkpoint(self, table: str):
        """The full checkpoint record for a table, or None if there is none yet."""
        return self._data.get(table)

    # --- writes (all thread-safe: concurrent table loads write distinct keys, one file) ---

    def begin(self, table: str) -> None:
        with self._lock:
            rec = self._data.setdefault(table, {"hwm": None, "rows": 0})
            rec["status"] = "in_progress"
            rec["updated_at"] = _now()
            self._flush()

    def advance(self, table: str, hwm, rows_delta: int) -> None:
        """Checkpoint after a committed batch: move the cursor and add the rows just loaded."""
        with self._lock:
            rec = self._data.setdefault(table, {"hwm": None, "rows": 0})
            rec["hwm"] = self._normalize(hwm)
            rec["rows"] = rec.get("rows", 0) + rows_delta
            rec["status"] = "in_progress"
            rec["updated_at"] = _now()
            self._flush()

    def complete(self, table: str) -> None:
        with self._lock:
            rec = self._data.setdefault(table, {"hwm": None, "rows": 0})
            rec["status"] = "complete"
            rec["updated_at"] = _now()
            self._flush()

    def reset(self, table: str) -> None:
        """Drop a table's checkpoint so the next run reloads it from scratch (`--restart`)."""
        with self._lock:
            if self._data.pop(table, None) is not None:
                self._flush()

    def set(self, table: str, value) -> None:
        """Set only the cursor (no row delta). Kept for callers that just move the watermark."""
        self.advance(table, value, 0)

    @staticmethod
    def _normalize(value):
        # Preserve native JSON scalar types (int/float/str/bool) so numeric watermarks
        # round-trip correctly; render date/datetime as ISO (sortable + JSON-safe).
        if value is None or isinstance(value, (int, float, str, bool)):
            return value
        iso = getattr(value, "isoformat", None)
        return iso() if callable(iso) else str(value)

    def _flush(self) -> None:
        # Atomic write: temp file + os.replace so a crash never leaves half-written state.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
            logger.debug("checkpoint flushed -> %s", self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
