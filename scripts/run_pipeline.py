#!/usr/bin/env python3
"""End-to-end orchestrator: deploy → ingest → transform → validate, in one command.

Runs the whole pipeline against the live account using the same scripts documented in the
demo. Idempotent: safe to re-run (deploys use IF NOT EXISTS; loads are watermark-incremental;
backfill uses INSERT OVERWRITE / MERGE). Fails loud on the first error.

Run:  python -m scripts.run_pipeline --num-patients 300
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("run_pipeline")
ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

TRANSFORM_STEPS = [  # DDL + procedures + backfill (the scheduled DAG lives in 06_tasks.sql)
    "00_streams", "01_staging", "02_marts_dims", "03_marts_fact",
    "04_procedures", "05_backfill", "07_analytics_views",
]

LOCAL_CONFIG = """source:
  type: file
  path: {data}/patients.csv
snowflake:
  connection: snowflake_pipeline
  database: HEALTH_ANALYTICS
  schema: RAW
masking:
  salt: snowflake-pipeline-synthetic
tables:
  - name: patients
    target: PATIENTS_CSV
    hwm_column: patient_id
    batch_size: 5000
    mask:
      ssn: ssn
      phone: phone
"""


def run(step: str, *args: str) -> None:
    logger.info("> %s", step)
    result = subprocess.run([PY, *args], cwd=ROOT)
    if result.returncode != 0:
        logger.error("step failed (exit %d): %s", result.returncode, step)
        sys.exit(result.returncode)


def main() -> int:
    p = argparse.ArgumentParser(description="Run the full pipeline end to end.")
    p.add_argument("--num-patients", type=int, default=300)
    p.add_argument("--data-dir", default="data/synthea")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    data = Path(args.data_dir)

    # 1. Foundation + RAW structures
    run("deploy foundation", "-m", "scripts.run_sql", "--dir", "sql/00_setup")
    run("file formats", "-m", "scripts.run_sql", "--file", "sql/10_ingest/01_file_formats.sql")
    run("raw tables", "-m", "scripts.run_sql", "--file", "sql/10_ingest/03_raw_tables.sql")

    # 2. Data
    run("generate data", "-m", "scripts.generate_synthetic_data",
        "--num-patients", str(args.num_patients), "--out-dir", str(data))

    # 3. Load (relational via loader, semi-structured via internal stage)
    cfg = ROOT / "config" / "loader.local.yaml"
    cfg.write_text(LOCAL_CONFIG.format(data=data.as_posix()), encoding="utf-8")
    run("load patients", "-m", "loader", "--config", "config/loader.local.yaml")
    run("load encounters", "-m", "scripts.load_internal_stage",
        "--file", f"{data}/encounters.json", "--table", "ENCOUNTERS_JSON", "--format", "json", "--truncate")

    # 4. Transform (backfill build)
    for step in TRANSFORM_STEPS:
        run(f"transform {step}", "-m", "scripts.run_sql", "--file", f"sql/30_transform/{step}.sql")

    # 5. Validate
    run("data quality", "-m", "scripts.data_quality")

    logger.info("[OK] pipeline complete: RAW -> STAGING -> MARTS built and validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
