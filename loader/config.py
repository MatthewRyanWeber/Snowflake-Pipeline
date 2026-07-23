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

    # Either a static 'tables' list OR a 'control' block (metadata-driven from GOV.SOURCES).
    if cfg.get("control"):
        if "source_group" not in cfg["control"]:
            raise ValueError("config.control missing 'source_group'")
        return
    tables = cfg.get("tables")
    if not tables:
        raise ValueError("config must define 'tables' or a 'control' section")
    for i, t in enumerate(tables):
        for key in ("name", "hwm_column"):
            if key not in t:
                raise ValueError(f"tables[{i}] missing '{key}'")
