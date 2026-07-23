"""Phase 4 · Snowpark cohort aggregation — naive vs optimized.

Same result two ways:
  - naive():     pulls whole tables to the client and joins/aggregates in pandas
                 (data leaves the warehouse; the client does the work).
  - optimized(): expresses the join+aggregation as a Snowpark DataFrame so the whole
                 computation is pushed down into Snowflake; only the small aggregated
                 result crosses the wire.

This is the honest analog to "Spark job optimization": Snowpark is Snowflake's Spark-style
DataFrame API, compiled to SQL and executed in the warehouse.

Run:  python snowpark/cohort_aggregation.py
"""

import logging
import time

from snowflake.snowpark import Session
from snowflake.snowpark.functions import avg, col, count, count_distinct
from snowflake.snowpark.functions import round as round_
from snowflake.snowpark.functions import sum as sum_

logger = logging.getLogger("cohort_aggregation")

DB = "HEALTH_ANALYTICS"


def get_session() -> Session:
    # Reuses ~/.snowflake/connections.toml (no credentials in code).
    return Session.builder.config("connection_name", "snowflake_pipeline").create()


def optimized(session: Session):
    """Join + aggregate pushed down; only the aggregated result is materialized client-side."""
    fact = session.table(f"{DB}.MARTS.FACT_ENCOUNTER")
    fac = session.table(f"{DB}.MARTS.DIM_FACILITY")
    loc = session.table(f"{DB}.MARTS.DIM_LOCATION")
    df = (
        fact.join(fac, fact["FACILITY_SK"] == fac["FACILITY_SK"])
        .join(loc, fac["LOCATION_SK"] == loc["LOCATION_SK"])
        .group_by(loc["REGION"], fact["ENCOUNTER_CLASS"])
        .agg(
            count("*").alias("ENCOUNTERS"),
            count_distinct(fact["PATIENT_SK"]).alias("PATIENTS"),
            round_(avg(fact["DURATION_MINUTES"]), 1).alias("AVG_MIN"),
            sum_(fact["OBSERVATION_COUNT"]).alias("TOTAL_OBS"),
        )
    )
    pdf = df.to_pandas()  # small: one row per (region, class)
    return pdf, {"rows_to_client": len(pdf)}


def naive(session: Session):
    """Anti-pattern: pull full tables to the client, then join/aggregate in pandas."""
    f = session.table(f"{DB}.MARTS.FACT_ENCOUNTER").to_pandas()
    fac = session.table(f"{DB}.MARTS.DIM_FACILITY").to_pandas()
    loc = session.table(f"{DB}.MARTS.DIM_LOCATION").to_pandas()
    m = f.merge(fac, on="FACILITY_SK").merge(loc, on="LOCATION_SK")
    g = (
        m.groupby(["REGION", "ENCOUNTER_CLASS"])
        .agg(
            ENCOUNTERS=("ENCOUNTER_ID", "size"),
            PATIENTS=("PATIENT_SK", "nunique"),
            AVG_MIN=("DURATION_MINUTES", "mean"),
            TOTAL_OBS=("OBSERVATION_COUNT", "sum"),
        )
        .reset_index()
    )
    g["AVG_MIN"] = g["AVG_MIN"].round(1)
    return g, {"rows_to_client": len(f) + len(fac) + len(loc)}


def _normalize(pdf):
    return (
        pdf.sort_values(["REGION", "ENCOUNTER_CLASS"])
        .reset_index(drop=True)[["REGION", "ENCOUNTER_CLASS", "ENCOUNTERS", "PATIENTS", "TOTAL_OBS"]]
    )


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    session = get_session()
    try:
        t0 = time.time()
        n_res, n_stats = naive(session)
        t1 = time.time()
        o_res, o_stats = optimized(session)
        t2 = time.time()

        same = _normalize(n_res).equals(_normalize(o_res))
        logger.info("results identical: %s", same)
        logger.info("naive:     %.2fs, rows pulled to client = %d",
                    t1 - t0, n_stats["rows_to_client"])
        logger.info("optimized: %.2fs, rows pulled to client = %d",
                    t2 - t1, o_stats["rows_to_client"])
        logger.info("client data movement reduced %.0fx",
                    n_stats["rows_to_client"] / max(o_stats["rows_to_client"], 1))
        print(_normalize(o_res).to_string(index=False))
        assert same, "naive and optimized results diverged"
    finally:
        session.close()


if __name__ == "__main__":
    main()
