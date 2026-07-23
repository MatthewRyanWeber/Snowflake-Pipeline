#!/usr/bin/env python3
"""Generate Synthea-shaped synthetic healthcare files for the ingestion pipeline.

Emits two artifacts that map onto the Phase 1 RAW tables:
  - patients.csv    : structured/relational rows (loaded to RAW.PATIENTS_CSV)
  - encounters.json : NDJSON, one object per line, with nested `observations` /
                      `conditions` arrays (loaded to RAW.ENCOUNTERS_JSON as VARIANT)

# ASSUMPTION: this is a dependency-free stand-in for Synthea so the pipeline is
# buildable/testable offline. Real Synthea output can replace these files unchanged —
# RAW only cares about the CSV columns and the JSON shape, not the producer.

Stdlib only (no third-party deps). Deterministic given --seed.
"""

import argparse
import csv
import json
import logging
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger("generate_synthetic_data")

# WHY: fixed vocabularies keep generated data realistic and joinable across records.
FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
               "Linda", "David", "Elizabeth", "Maria", "Wei", "Aisha", "Diego", "Yuki"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
              "Davis", "Rodriguez", "Martinez", "Chen", "Okafor", "Nguyen", "Patel"]
STATES = ["NY", "NJ", "CT", "PA", "MA", "CA", "TX", "IL"]
ENCOUNTER_CLASSES = ["ambulatory", "emergency", "inpatient", "wellness", "urgentcare"]
PROVIDERS = ["Dr. Alvarez", "Dr. Bianchi", "Dr. Cohen", "Dr. Dubois", "Dr. Eze"]
FACILITIES = [
    {"facility_id": "FAC-001", "name": "Riverside General", "city": "New York", "state": "NY"},
    {"facility_id": "FAC-002", "name": "Lakeside Medical", "city": "Newark", "state": "NJ"},
    {"facility_id": "FAC-003", "name": "Summit Health", "city": "Hartford", "state": "CT"},
]
# (code, description, units, low, high) — clinical observation catalog.
OBS_CATALOG = [
    ("8867-4", "Heart rate", "/min", 55, 105),
    ("8480-6", "Systolic blood pressure", "mm[Hg]", 100, 160),
    ("8462-4", "Diastolic blood pressure", "mm[Hg]", 60, 100),
    ("2339-0", "Glucose", "mg/dL", 70, 180),
    ("39156-5", "Body mass index", "kg/m2", 18, 38),
    ("8310-5", "Body temperature", "Cel", 36, 39),
]
CONDITIONS = [
    ("38341003", "Hypertension"), ("44054006", "Diabetes"), ("195967001", "Asthma"),
    ("40055000", "Chronic sinusitis"), ("162864005", "Obesity"), (None, None),
]


def _rand_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _ssn(rng: random.Random) -> str:
    # WHY: synthetic-only; realistic shape so masking controls have something to mask later.
    return f"{rng.randint(100, 899):03d}-{rng.randint(10, 99):02d}-{rng.randint(1000, 9999):04d}"


def _phone(rng: random.Random) -> str:
    return f"({rng.randint(200, 989):03d}) {rng.randint(200, 989):03d}-{rng.randint(1000, 9999):04d}"


def generate(num_patients: int, enc_min: int, enc_max: int, seed: int):
    rng = random.Random(seed)
    patients = []
    encounters = []
    for i in range(1, num_patients + 1):
        pid = f"PAT-{i:06d}"
        state = rng.choice(STATES)
        patients.append({
            "patient_id": pid,
            "first_name": rng.choice(FIRST_NAMES),
            "last_name": rng.choice(LAST_NAMES),
            "birth_date": _rand_date(rng, date(1940, 1, 1), date(2015, 12, 31)).isoformat(),
            "gender": rng.choice(["M", "F"]),
            "ssn": _ssn(rng),
            "address": f"{rng.randint(1, 9999)} {rng.choice(LAST_NAMES)} St",
            "city": rng.choice(["New York", "Newark", "Hartford", "Boston", "Albany"]),
            "state": state,
            "zip": f"{rng.randint(6000, 19999):05d}",
            "phone": _phone(rng),
        })

        for _ in range(rng.randint(enc_min, enc_max)):
            start = datetime.combine(_rand_date(rng, date(2023, 1, 1), date(2025, 12, 31)),
                                     datetime.min.time()) + timedelta(hours=rng.randint(7, 19))
            stop = start + timedelta(minutes=rng.randint(15, 240))
            facility = rng.choice(FACILITIES)
            observations = []
            for code, desc, units, low, high in rng.sample(OBS_CATALOG, rng.randint(1, len(OBS_CATALOG))):
                observations.append({
                    "code": code, "description": desc,
                    "value": round(rng.uniform(low, high), 1), "units": units,
                })
            cond_code, cond_desc = rng.choice(CONDITIONS)
            conditions = [] if cond_code is None else [{"code": cond_code, "description": cond_desc}]
            encounters.append({
                "encounter_id": f"ENC-{rng.randint(10**9, 10**10 - 1)}",
                "patient_id": pid,
                "start": start.isoformat(),
                "stop": stop.isoformat(),
                "encounter_class": rng.choice(ENCOUNTER_CLASSES),
                "provider": {"name": rng.choice(PROVIDERS),
                             "facility_id": facility["facility_id"],
                             "facility_name": facility["name"],
                             "city": facility["city"], "state": facility["state"]},
                "observations": observations,
                "conditions": conditions,
            })
    return patients, encounters


def write_csv(patients: list, path: Path) -> None:
    cols = ["patient_id", "first_name", "last_name", "birth_date", "gender", "ssn",
            "address", "city", "state", "zip", "phone"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(patients)
    logger.info("wrote %d patients -> %s", len(patients), path)


def write_ndjson(encounters: list, path: Path) -> None:
    # WHY: NDJSON (one object per line) loads cleanly into a VARIANT column without
    # STRIP_OUTER_ARRAY, and streams row-by-row for Snowpipe.
    with path.open("w", encoding="utf-8") as fh:
        for enc in encounters:
            fh.write(json.dumps(enc, separators=(",", ":")) + "\n")
    logger.info("wrote %d encounters -> %s", len(encounters), path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate Synthea-shaped synthetic health data.")
    p.add_argument("--out-dir", default="data/synthea", type=Path, help="output directory")
    p.add_argument("--num-patients", type=int, default=200)
    p.add_argument("--encounters-min", type=int, default=1)
    p.add_argument("--encounters-max", type=int, default=6)
    p.add_argument("--seed", type=int, default=42, help="deterministic RNG seed")
    p.add_argument("--format", choices=["csv", "json", "both"], default="both")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if args.encounters_min > args.encounters_max:
        logger.error("--encounters-min (%d) > --encounters-max (%d)", args.encounters_min, args.encounters_max)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    patients, encounters = generate(args.num_patients, args.encounters_min,
                                    args.encounters_max, args.seed)

    if args.format in ("csv", "both"):
        write_csv(patients, args.out_dir / "patients.csv")
    if args.format in ("json", "both"):
        write_ndjson(encounters, args.out_dir / "encounters.json")

    logger.info("done: %d patients, %d encounters (seed=%d) -> %s",
                len(patients), len(encounters), args.seed, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
