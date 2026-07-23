"""Centralized logging: console (INFO+) plus a rotating file (DEBUG+) under logs/."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def configure(log_dir: Path = Path("logs"), verbose: bool = False) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s", "%Y-%m-%dT%H:%M:%S%z"
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 50MB x 5 backups, full debug detail on disk.
    fileh = RotatingFileHandler(
        log_dir / "loader.log", maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fileh.setLevel(logging.DEBUG)
    fileh.setFormatter(fmt)
    root.addHandler(fileh)

    _CONFIGURED = True
