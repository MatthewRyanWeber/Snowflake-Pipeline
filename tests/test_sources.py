"""Source unit tests — Excel, Parquet, and REST honour the fetch_batches / count contract:
full load, incremental (since) filter, batching, and ascending order for safe checkpointing.
Run: python -m pytest tests/ -q

Postgres and MySQL need a live server; they're verified separately against Docker containers
(see docs/sources.md), so they're not exercised here.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loader.source_excel import ExcelSource  # noqa: E402
from loader.source_parquet import ParquetSource  # noqa: E402
from loader.source_rest import RestSource  # noqa: E402

ROWS = [
    {"id": 1, "name": "a", "ts": 10},
    {"id": 2, "name": "b", "ts": 20},
    {"id": 3, "name": "c", "ts": 30},
    {"id": 4, "name": "d", "ts": 40},
]


def _flatten(batches):
    return [r for b in batches for r in b]


# --- Excel ---

def _write_xlsx(path, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "records"
    ws.append(list(rows[0].keys()))
    for r in rows:
        ws.append(list(r.values()))
    wb.save(path)


def test_excel_full_and_incremental(tmp_path):
    p = tmp_path / "src.xlsx"
    _write_xlsx(p, ROWS)
    src = ExcelSource(str(p)).connect()

    assert src.count("records", "ts", None) == 4
    got = _flatten(src.fetch_batches("records", "ts", None, batch_size=2))
    assert [r["id"] for r in got] == [1, 2, 3, 4]  # ascending by hwm

    assert src.count("records", "ts", 20) == 2
    inc = _flatten(src.fetch_batches("records", "ts", 20, batch_size=10))
    assert [r["id"] for r in inc] == [3, 4]


def test_excel_batching(tmp_path):
    p = tmp_path / "src.xlsx"
    _write_xlsx(p, ROWS)
    src = ExcelSource(str(p)).connect()
    batches = list(src.fetch_batches("records", "ts", None, batch_size=2))
    assert [len(b) for b in batches] == [2, 2]


# --- Parquet ---

def _write_parquet(path, rows):
    import pyarrow as pa
    import pyarrow.parquet as pq

    # Write intentionally out of order to prove the source sorts by hwm.
    shuffled = [rows[2], rows[0], rows[3], rows[1]]
    table = pa.Table.from_pylist(shuffled)
    pq.write_table(table, path)


def test_parquet_full_and_incremental(tmp_path):
    p = tmp_path / "src.parquet"
    _write_parquet(p, ROWS)
    src = ParquetSource(str(p)).connect()

    assert src.count("records", "ts", None) == 4
    got = _flatten(src.fetch_batches("records", "ts", None, batch_size=3))
    assert [r["id"] for r in got] == [1, 2, 3, 4]  # sorted ascending despite unsorted file

    assert src.count("records", "ts", 20) == 2
    inc = _flatten(src.fetch_batches("records", "ts", 20, batch_size=10))
    assert [r["id"] for r in inc] == [3, 4]


# --- REST ---

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        limit = int(q.get("limit", ["50"])[0])
        offset = int(q.get("offset", ["0"])[0])
        rows = ROWS
        if "ts_gt" in q:
            rows = [r for r in rows if r["ts"] > int(q["ts_gt"][0])]
        page = rows[offset:offset + limit]
        body = json.dumps(page).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Total-Count", str(len(rows)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence test server
        pass


def _serve():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def test_rest_paginates_and_counts():
    httpd, port = _serve()
    try:
        src = RestSource(base_url=f"http://127.0.0.1:{port}").connect()
        assert src.count("records", "ts", None) == 4
        got = _flatten(src.fetch_batches("records", "ts", None, batch_size=2))
        assert [r["id"] for r in got] == [1, 2, 3, 4]  # two pages of 2

        assert src.count("records", "ts", 20) == 2
        inc = _flatten(src.fetch_batches("records", "ts", 20, batch_size=10))
        assert [r["id"] for r in inc] == [3, 4]
    finally:
        httpd.shutdown()
