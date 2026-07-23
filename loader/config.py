"""Load and validate config/loader.yaml. No secrets live here — only names and policies."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_config(path: Path = Path("config/loader.yaml")) -> dict:
    import yaml  # pyyaml is a light, always-present dependency

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"loader config not found: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    if "snowflake" not in cfg:
        raise ValueError("config missing 'snowflake' section")
    for key in ("connection", "database", "schema"):
        if key not in cfg["snowflake"]:
            raise ValueError(f"config.snowflake missing '{key}'")

    tables = cfg.get("tables")
    if not tables:
        raise ValueError("config must define at least one table under 'tables'")
    for i, t in enumerate(tables):
        for key in ("name", "hwm_column"):
            if key not in t:
                raise ValueError(f"tables[{i}] missing '{key}'")
