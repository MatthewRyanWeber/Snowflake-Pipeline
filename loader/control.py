"""Metadata-driven ingestion: read the table work-list from the GOV.SOURCES control table.

Adding a table to the pipeline becomes an INSERT into GOV.SOURCES, not a code or config change.
Connection details still come from config (secrets never live in the control table); only the
*what to load* (source table, target, hwm column, batch size, masking) is data-driven.
"""

import json
import logging

logger = logging.getLogger(__name__)


def load_tables_from_control(sf: dict, source_group: str) -> list:
    import snowflake.connector as sc

    con = sc.connect(connection_name=sf["connection"], database=sf["database"])
    try:
        cur = con.cursor()
        rows = cur.execute(
            "SELECT source_table, target_table, hwm_column, batch_size, mask "
            "FROM GOV.SOURCES WHERE source_group = %s AND enabled ORDER BY source_table",
            (source_group,),
        ).fetchall()
    finally:
        con.close()

    tables = []
    for source_table, target, hwm_column, batch_size, mask in rows:
        cfg = {
            "name": source_table,
            "target": target,
            "hwm_column": hwm_column,
            "batch_size": int(batch_size or 5000),
        }
        if mask:  # VARIANT comes back as a JSON string
            cfg["mask"] = mask if isinstance(mask, dict) else json.loads(mask)
        tables.append(cfg)
    logger.info("control: %d table(s) from GOV.SOURCES (group=%s)", len(tables), source_group)
    return tables
