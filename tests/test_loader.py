"""Loader unit tests — masking, watermark checkpointing, incremental pipeline, file source.
Run: python -m pytest tests/ -q"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loader import masking  # noqa: E402
from loader.pipeline import run  # noqa: E402
from loader.source_file import FileSource  # noqa: E402
from loader.watermark import WatermarkStore  # noqa: E402


# --- masking ---

def test_mask_ssn_keeps_last4():
    assert masking.mask_ssn("123-45-6789") == "XXX-XX-6789"
    assert masking.mask_ssn("") == ""
    assert masking.mask_ssn(None) is None


def test_mask_phone_keeps_last4():
    assert masking.mask_phone("(212) 555-1234") == "(XXX) XXX-1234"


def test_hash_is_deterministic_and_nonreversible():
    a = masking.hash_sha256("PAT-1", salt="s")
    b = masking.hash_sha256("PAT-1", salt="s")
    assert a == b and a != "PAT-1" and len(a) == 64


def test_unknown_policy_raises():
    try:
        masking.apply_policy("x", "nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_mask_row_only_touches_configured_columns():
    row = {"patient_id": "PAT-1", "ssn": "123-45-6789", "city": "NYC"}
    out = masking.mask_row(row, {"ssn": "ssn"}, salt="s")
    assert out["ssn"] == "XXX-XX-6789"
    assert out["city"] == "NYC" and out["patient_id"] == "PAT-1"


# --- watermark ---

def test_watermark_persists_and_reloads(tmp_path):
    p = tmp_path / "wm.json"
    wm = WatermarkStore(p)
    assert wm.get("patients") is None
    wm.set("patients", "PAT-000010")
    assert WatermarkStore(p).get("patients") == "PAT-000010"


def test_corrupt_watermark_fails_loud(tmp_path):
    p = tmp_path / "wm.json"
    p.write_text("{not json", encoding="utf-8")
    try:
        WatermarkStore(p)
        assert False, "expected RuntimeError on corrupt state"
    except RuntimeError:
        pass


# --- pipeline (with fakes) ---

class FakeSource:
    def __init__(self, rows):
        self._rows = rows

    def fetch_batches(self, table, hwm_column, since, batch_size):
        rows = sorted(self._rows, key=lambda r: r[hwm_column])
        if since is not None:
            rows = [r for r in rows if str(r[hwm_column]) > str(since)]
        for i in range(0, len(rows), batch_size):
            yield rows[i:i + batch_size]


class FakeSink:
    def __init__(self):
        self.written = []

    def write(self, table, rows):
        self.written.extend(rows)
        return len(rows)

    def close(self):
        pass


def _rows(n):
    return [{"patient_id": f"PAT-{i:06d}", "ssn": "123-45-6789", "city": "NYC"} for i in range(1, n + 1)]


def test_pipeline_masks_and_writes():
    src, sink = FakeSource(_rows(5)), FakeSink()
    wm = WatermarkStore(Path("state/_test_wm1.json"))
    wm._data = {}
    cfg = [{"name": "patients", "target": "PATIENTS_CSV", "hwm_column": "patient_id",
            "batch_size": 2, "mask": {"ssn": "ssn"}}]
    res = run(src, sink, wm, cfg, salt="s")[0]
    assert res.rows_read == 5 and res.rows_written == 5
    assert all(r["ssn"] == "XXX-XX-6789" for r in sink.written)
    Path("state/_test_wm1.json").unlink(missing_ok=True)


def test_dry_run_writes_nothing_and_leaves_watermark(tmp_path):
    src, sink = FakeSource(_rows(3)), FakeSink()
    wm = WatermarkStore(tmp_path / "wm.json")
    cfg = [{"name": "patients", "hwm_column": "patient_id", "batch_size": 10}]
    res = run(src, sink, wm, cfg, salt="s", dry_run=True)[0]
    assert res.rows_read == 3 and res.rows_written == 0
    assert sink.written == []
    assert wm.get("patients") is None  # dry-run must not advance the checkpoint


def test_incremental_resumes_from_watermark(tmp_path):
    wm = WatermarkStore(tmp_path / "wm.json")
    sink = FakeSink()
    cfg = [{"name": "patients", "hwm_column": "patient_id", "batch_size": 10}]
    run(FakeSource(_rows(3)), sink, wm, cfg, salt="s")            # loads PAT-000001..3
    first = len(sink.written)
    run(FakeSource(_rows(5)), sink, wm, cfg, salt="s")            # only PAT-000004..5 are new
    assert len(sink.written) - first == 2


# --- file source (offline end-to-end) ---

def test_progress_estimates_eta():
    from loader.progress import Progress, format_duration
    now = [0.0]
    p = Progress(total=1000, label="t", min_interval=0, clock=lambda: now[0])
    now[0] = 1.0
    p.update(250)                       # 250 rows in 1s -> 750 left at 250/s -> 3s
    assert p.done == 250
    assert abs(p.eta_seconds() - 3.0) < 0.01
    assert format_duration(3) == "3s" and format_duration(125) == "2m05s"


def test_progress_handles_unknown_total():
    from loader.progress import Progress
    p = Progress(total=None, label="t", min_interval=0, clock=lambda: 0.0)
    p.update(10)                        # must not divide-by-total or raise
    p.finish()
    assert p.done == 10 and p.eta_seconds() == float("inf")


def test_file_source_count_matches_fetch(tmp_path):
    import csv as _csv
    from loader.source_file import FileSource
    path = tmp_path / "p.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=["patient_id"])
        w.writeheader()
        for i in range(1, 8):
            w.writerow({"patient_id": f"PAT-{i:03d}"})
    src = FileSource(path).connect()
    assert src.count("p", "patient_id", None) == 7
    assert src.count("p", "patient_id", "PAT-005") == 2


def test_watermark_preserves_native_int():
    from loader.watermark import WatermarkStore
    import tempfile, os
    d = tempfile.mkdtemp()
    p = Path(d) / "wm.json"
    WatermarkStore(p).set("t", 100)
    got = WatermarkStore(p).get("t")
    assert got == 100 and isinstance(got, int)  # not the string "100"
    os.remove(p)


def test_masking_tolerates_non_string_value():
    assert masking.mask_ssn(123456789) == "XXX-XX-6789"      # int, not str
    assert masking.mask_ssn("") == "" and masking.mask_ssn(None) is None


def test_load_table_rejects_injection_identifier(tmp_path):
    from loader.pipeline import load_table
    wm = WatermarkStore(tmp_path / "wm.json")
    bad = {"name": "patients; DROP TABLE x", "hwm_column": "patient_id"}
    try:
        load_table(FakeSource([]), FakeSink(), wm, bad, salt="s")
        assert False, "expected ValueError on unsafe identifier"
    except ValueError:
        pass


def test_sqlite_source_reads_and_filters(tmp_path):
    import sqlite3
    from loader.source_sqlite import SqliteSource
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE patients (patient_id TEXT, ssn TEXT)")
    con.executemany("INSERT INTO patients VALUES (?,?)",
                    [(f"PAT-{i:03d}", "123-45-6789") for i in range(1, 6)])
    con.commit(); con.close()

    src = SqliteSource(db).connect()
    rows = [r for b in src.fetch_batches("patients", "patient_id", None, 2) for r in b]
    assert len(rows) == 5 and rows[0]["patient_id"] == "PAT-001"
    # incremental filter
    rows2 = [r for b in src.fetch_batches("patients", "patient_id", "PAT-003", 10) for r in b]
    assert [r["patient_id"] for r in rows2] == ["PAT-004", "PAT-005"]
    src.close()


def test_file_source_reads_sample_csv():
    sample = Path(__file__).resolve().parents[1] / "sql/10_ingest/samples/patients.csv"
    if not sample.exists():
        return  # sample optional
    src = FileSource(sample).connect()
    batches = list(src.fetch_batches("patients", "patient_id", None, 2))
    rows = [r for b in batches for r in b]
    assert rows and "ssn" in rows[0]
    ids = [r["patient_id"] for r in rows]
    assert ids == sorted(ids)  # ordered by hwm
