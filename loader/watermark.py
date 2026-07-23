"""High-water-mark store — persisted checkpoints for incremental, resumable loads.

Each table's last successfully-loaded HWM value is written to a JSON state file after
every committed batch. A crash mid-load resumes from the last checkpoint, never
reloading committed rows and never skipping uncommitted ones.
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class WatermarkStore:
    def __init__(self, path: Path = Path("state/watermarks.json")):
        self.path = Path(path)
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()   # parallel table loads share one store
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                # Corrupt state must not silently reset to a full reload — fail loud.
                raise RuntimeError(f"unreadable watermark state {self.path}: {exc}") from exc
        else:
            self._data = {}

    def get(self, table: str):
        return self._data.get(table)

    def set(self, table: str, value) -> None:
        with self._lock:   # thread-safe: concurrent table loads write distinct keys, one file
            self._data[table] = self._normalize(value)
            self._flush()

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
            logger.debug("watermark flushed -> %s", self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
