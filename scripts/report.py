"""Reporting CLI — print a MARTS analytics view as an aligned table.

  python -m scripts.report revenue-by-payer
  python -m scripts.report claim-exposure --limit 10
"""

import argparse
from decimal import Decimal

from . import _cli

VIEWS = {
    "revenue-by-payer":       "MARTS.VW_REVENUE_BY_PAYER",
    "revenue-by-region":      "MARTS.VW_REVENUE_BY_REGION",
    "claim-exposure":         "MARTS.VW_CLAIM_STATUS_EXPOSURE",
    "encounters-by-region":   "MARTS.VW_ENCOUNTERS_BY_REGION",
    "provider-productivity":  "MARTS.VW_PROVIDER_PRODUCTIVITY",
    "monthly-trend":          "MARTS.VW_MONTHLY_ENCOUNTER_TREND",
}


def _fmt(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, Decimal):
        return f"{v:,.2f}"
    return "" if v is None else str(v)


def main() -> int:
    p = _cli.add_common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("view", choices=sorted(VIEWS), help="which analytics view to print")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    _cli.setup_logging(args.verbose)

    con = _cli.connect(args)
    cur = con.cursor()
    cur.execute("USE WAREHOUSE PIPELINE_WH")
    rows = cur.execute(f"SELECT * FROM {VIEWS[args.view]} LIMIT {args.limit}").fetchall()
    cols = [c[0].lower() for c in cur.description]
    con.close()

    widths = [max(len(cols[i]), max((len(_fmt(r[i])) for r in rows), default=0)) for i in range(len(cols))]
    print("  ".join(c.ljust(widths[i]) for i, c in enumerate(cols)))
    print("  ".join("-" * widths[i] for i in range(len(cols))))
    for r in rows:
        print("  ".join(_fmt(r[i]).ljust(widths[i]) for i in range(len(cols))))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
