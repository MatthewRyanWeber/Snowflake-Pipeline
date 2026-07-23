"""Smoke tests for the synthetic data generator. Run: python -m pytest tests/ -q"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import generate_synthetic_data as gen  # noqa: E402


def test_deterministic_given_seed():
    a = gen.generate(num_patients=10, enc_min=1, enc_max=4, seed=123)
    b = gen.generate(num_patients=10, enc_min=1, enc_max=4, seed=123)
    assert a == b, "same seed must produce identical data"


def test_patient_ids_unique_and_referenced():
    patients, encounters = gen.generate(num_patients=20, enc_min=1, enc_max=3, seed=1)
    pids = {p["patient_id"] for p in patients}
    assert len(pids) == 20
    # Every encounter references a real patient — RAW joins depend on this.
    assert {e["patient_id"] for e in encounters}.issubset(pids)


def test_encounters_have_flattenable_arrays():
    _, encounters = gen.generate(num_patients=15, enc_min=2, enc_max=5, seed=2)
    assert encounters, "expected some encounters"
    assert any(e["observations"] for e in encounters), "need non-empty observations for FLATTEN"
    for e in encounters:
        assert isinstance(e["observations"], list)
        assert isinstance(e["conditions"], list)
        assert "provider" in e and "name" in e["provider"]


def test_writes_valid_csv_and_ndjson(tmp_path):
    patients, encounters = gen.generate(num_patients=8, enc_min=1, enc_max=3, seed=99)
    csv_path = tmp_path / "patients.csv"
    json_path = tmp_path / "encounters.json"
    gen.write_csv(patients, csv_path)
    gen.write_ndjson(encounters, json_path)

    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 8
    assert rows[0]["patient_id"].startswith("PAT-")

    # NDJSON: every line is a standalone JSON object.
    with json_path.open(encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert len(lines) == len(encounters)
