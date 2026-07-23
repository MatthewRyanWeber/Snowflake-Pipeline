"""Data-quality gate — asserts integrity + governance invariants against the live warehouse.

Each check is a SQL query that must return 0 (a count of violations). Non-zero = failure;
the script exits non-zero so it can gate CI or a post-load step. Fail loud, never silent.

Run:  python scripts/data_quality.py [--connection NAME] [--database DB]
"""

import argparse
import logging
import sys

import _cli

logger = logging.getLogger("data_quality")
DB = "HEALTH_ANALYTICS"

# name -> SQL returning a single count of VIOLATIONS (0 = pass).
CHECKS = {
    "fact.patient_sk not null":   f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER WHERE patient_sk IS NULL",
    "fact.facility_sk not null":  f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER WHERE facility_sk IS NULL",
    "fact.provider_sk not null":  f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER WHERE provider_sk IS NULL",
    "fact.date_key not null":     f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER WHERE date_key IS NULL",
    "fact.patient_sk FK valid":   f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER f LEFT JOIN {DB}.MARTS.DIM_PATIENT d ON d.patient_sk=f.patient_sk WHERE f.patient_sk IS NOT NULL AND d.patient_sk IS NULL",
    "fact.facility_sk FK valid":  f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER f LEFT JOIN {DB}.MARTS.DIM_FACILITY d ON d.facility_sk=f.facility_sk WHERE d.facility_sk IS NULL",
    "fact.date_key FK valid":     f"SELECT COUNT(*) FROM {DB}.MARTS.FACT_ENCOUNTER f LEFT JOIN {DB}.MARTS.DIM_DATE d ON d.date_key=f.date_key WHERE d.date_key IS NULL",
    "dim_patient one current":    f"SELECT COUNT(*) FROM (SELECT patient_id FROM {DB}.MARTS.DIM_PATIENT WHERE is_current GROUP BY patient_id HAVING COUNT(*) > 1)",
    "dim_facility -> location FK": f"SELECT COUNT(*) FROM {DB}.MARTS.DIM_FACILITY f LEFT JOIN {DB}.MARTS.DIM_LOCATION l ON l.location_sk=f.location_sk WHERE l.location_sk IS NULL",
    "dim_location region set":    f"SELECT COUNT(*) FROM {DB}.MARTS.DIM_LOCATION WHERE region IS NULL",
    "RAW.ssn masked":             f"SELECT COUNT(*) FROM {DB}.RAW.PATIENTS_CSV WHERE ssn IS NOT NULL AND ssn NOT LIKE 'XXX-XX-%'",
    "RAW.phone masked":           f"SELECT COUNT(*) FROM {DB}.RAW.PATIENTS_CSV WHERE phone IS NOT NULL AND phone NOT LIKE '(XXX) XXX-%'",
}


def main() -> int:
    args = _cli.add_common_args(argparse.ArgumentParser(description=__doc__)).parse_args()
    _cli.setup_logging(args.verbose)
    con = _cli.connect(args)
    cur = con.cursor()
    cur.execute("USE WAREHOUSE PIPELINE_WH")
    failures = 0
    try:
        for name, sql in CHECKS.items():
            violations = cur.execute(sql).fetchone()[0]
            status = "PASS" if violations == 0 else "FAIL"
            if violations:
                failures += 1
            logger.info("[%s] %-28s violations=%d", status, name, violations)
    finally:
        cur.close()
        con.close()
    logger.info("%d/%d checks passed", len(CHECKS) - failures, len(CHECKS))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
