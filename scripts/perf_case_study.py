"""Phase 5 · Performance tuning case study — micro-partition pruning.

Builds two copies of a large fact table from the same rows:
  - FACT_BIG_RANDOM: rows in random order (poor natural clustering on date_key)
  - FACT_BIG_SORTED: rows physically ordered by date_key at load (CTAS ... ORDER BY)

Runs the SAME date-range-filtered query on each and reports partitions scanned / total from
the Query Profile. Ordering on the filter column lets Snowflake prune micro-partitions.

Run:  python scripts/perf_case_study.py --rowcount 2000
"""

import argparse
import json
import logging

import snowflake.connector as sc

logger = logging.getLogger("perf_case_study")
DB = "HEALTH_ANALYTICS"

FILTER = "date_key BETWEEN 20250101 AND 20250131"


def scan_stats(cur) -> tuple:
    row = cur.execute(
        "SELECT OPERATOR_STATISTICS:pruning:partitions_scanned::int, "
        "OPERATOR_STATISTICS:pruning:partitions_total::int "
        "FROM TABLE(GET_QUERY_OPERATOR_STATS(LAST_QUERY_ID())) "
        "WHERE OPERATOR_TYPE = 'TableScan' "
        "ORDER BY OPERATOR_STATISTICS:pruning:partitions_total::int DESC NULLS LAST LIMIT 1"
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def build_and_measure(cur, name: str, order_by: str | None, rowcount: int):
    order_clause = f"ORDER BY {order_by}" if order_by else ""
    # `pad` widens each row (~300 incompressible bytes) so the table spans many
    # micro-partitions at a modest row count — otherwise everything fits in 1-2 partitions
    # and there's nothing to prune.
    cur.execute(f"""
        CREATE OR REPLACE TABLE {DB}.MARTS.{name} AS
        SELECT f.encounter_id || '-' || g.n AS encounter_id,
               dd.date_key, f.patient_sk, f.provider_sk, f.facility_sk,
               f.encounter_class, f.duration_minutes, f.observation_count, f.condition_count,
               RANDSTR(300, RANDOM()) AS pad
        FROM {DB}.MARTS.FACT_ENCOUNTER f
        CROSS JOIN (SELECT SEQ4() n, UNIFORM(1, 1461, RANDOM()) rk
                    FROM TABLE(GENERATOR(ROWCOUNT => {rowcount}))) g
        JOIN (SELECT date_key, ROW_NUMBER() OVER (ORDER BY date_key) rn
              FROM {DB}.MARTS.DIM_DATE) dd ON dd.rn = g.rk
        {order_clause}
    """)
    total_rows = cur.execute(f"SELECT COUNT(*) FROM {DB}.MARTS.{name}").fetchone()[0]
    # Selective query — one month out of four years.
    cur.execute(f"SELECT COUNT(*), AVG(duration_minutes) FROM {DB}.MARTS.{name} WHERE {FILTER}")
    scanned, total = scan_stats(cur)
    ci = cur.execute(
        f"SELECT SYSTEM$CLUSTERING_INFORMATION('{DB}.MARTS.{name}', '(date_key)')"
    ).fetchone()[0]
    depth = json.loads(ci).get("average_depth")
    logger.info("%-16s rows=%d  partitions_scanned=%s/%s  avg_clustering_depth=%.2f",
                name, total_rows, scanned, total, depth)
    return {"name": name, "rows": total_rows, "scanned": scanned, "total": total, "depth": depth}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rowcount", type=int, default=2000, help="fan-out multiplier (x ~1024 fact rows)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    con = sc.connect(connection_name="snowflake_pipeline", database=DB)
    cur = con.cursor()
    try:
        cur.execute("USE WAREHOUSE PIPELINE_WH")
        cur.execute("ALTER SESSION SET USE_CACHED_RESULT = FALSE")  # measure real scans
        rnd = build_and_measure(cur, "FACT_BIG_RANDOM", None, args.rowcount)
        srt = build_and_measure(cur, "FACT_BIG_SORTED", "date_key", args.rowcount)
        if rnd["scanned"] and srt["scanned"]:
            logger.info("PRUNING WIN: sorted scans %s vs random %s partitions (%.1fx fewer)",
                        srt["scanned"], rnd["scanned"], rnd["scanned"] / max(srt["scanned"], 1))
    finally:
        # Always drop the big tables, even if a build/measure step raised, so a failed
        # run never leaves multi-GB tables behind.
        for t in ("FACT_BIG_RANDOM", "FACT_BIG_SORTED"):
            try:
                cur.execute(f"DROP TABLE IF EXISTS {DB}.MARTS.{t}")
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup, log and move on
                logger.warning("cleanup: could not drop %s: %s", t, exc)
        cur.close()
        con.close()


if __name__ == "__main__":
    main()
