"""Portable advisory file lock — prevents two loader runs clobbering shared state.

Uses atomic O_CREAT|O_EXCL lock-file creation (works on Windows + Linux, no fcntl/msvcrt
divergence). Stale locks from a crashed run are detectable via the recorded PID.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class LockHeldError(RuntimeError):
    pass


class FileLock:
    def __init__(self, path: Path = Path("state/loader.lock")):
        self.path = Path(path)
        self._fd = None

    def acquire(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            holder = self._read_holder()
            raise LockHeldError(
                f"another loader run holds {self.path} (pid {holder}). "
                f"If that process is dead, delete the lock file and retry."
            )
        os.write(self._fd, str(os.getpid()).encode("ascii"))
        logger.debug("lock acquired: %s (pid %d)", self.path, os.getpid())
        return self

    def _read_holder(self) -> str:
        try:
            return self.path.read_text(encoding="ascii").strip() or "unknown"
        except OSError:
            return "unknown"

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        logger.debug("lock released: %s", self.path)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
