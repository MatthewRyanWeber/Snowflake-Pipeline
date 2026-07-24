"""High-water-mark ordering — one comparison shared by every in-memory source.

The DB sources let SQL do `WHERE hwm > since ORDER BY hwm`, so ordering is the database's
job. The in-memory sources (CSV, Excel) must reproduce that ordering themselves, and doing it
by string comparison silently loses rows: `"10" > "9"` is False, so an incremental load past
id 9 would drop id 10. Compare numerically when both values are numeric, fall back to string
only for genuinely non-numeric keys — and use the SAME rule for the sort and the filter so they
never disagree.
"""


def _numeric(value):
    """(True, float) if value is numeric, else (False, str) — a sortable, comparable pair."""
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value))


def hwm_key(value):
    """Sort key: numeric keys order numerically, non-numeric fall back to string order."""
    return _numeric(value)


def hwm_gt(value, since) -> bool:
    """True if value > since under the same ordering as hwm_key (numeric-aware)."""
    return _numeric(value) > _numeric(since)
