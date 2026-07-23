"""Phase 2 · Relational-source loader: SQL Server -> Snowflake RAW.

Incremental (high-water-mark), idempotent, PII-masked on load, dry-run capable.
Heavy drivers (pyodbc, snowflake-connector) are imported lazily so the pure logic
(masking, watermark, orchestration) is testable without them installed.
"""

__version__ = "0.1.0"
