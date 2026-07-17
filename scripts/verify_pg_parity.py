r"""Verify Fabric vs Postgres WH_Silver mirror parity (Phase F, read-only).

Re-runnable version of the Phase F deep-audit parity check — catches schema
drift between Fabric and the Postgres fallback mirror before it can bite a
CEO question mid-fallback.

Checks per table (schema SAPHANADB by default):
- column names match (with NAMEDATALEN 63-char truncation-suspect detection)
- row counts match (skip with --skip-rowcount for a fast structural pass)
- data-type differences reported as informational (the mirror intentionally
  casts a few money/rate columns to numeric)

Requires BOTH live sources configured in .env (FABRIC_* and PG_REPLICA_*).
Runs SELECT-only statements on both sides — never any write.

Usage (repo root):
  $env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\verify_pg_parity.py
  ... scripts\verify_pg_parity.py --schema SAPHANADB --skip-rowcount
  ... scripts\verify_pg_parity.py --json data\local\exports\pg_parity.json

Exit codes: 0 = parity OK (type diffs allowed) · 1 = drift found · 2 = cannot run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.schema_parity import (  # noqa: E402
    build_parity_report,
    fetch_fabric_table_meta,
    fetch_pg_table_meta,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--schema", default="SAPHANADB", help="Schema to compare (default: SAPHANADB)")
    parser.add_argument("--skip-rowcount", action="store_true", help="Structure-only (skip COUNT(*) per table)")
    parser.add_argument("--json", dest="json_path", default="", help="Write full JSON report to this path")
    args = parser.parse_args()

    from backend.app.services.fabric_connector import get_fabric_connector
    from backend.app.services.postgres_replica import get_postgres_connector

    if not get_fabric_connector().is_configured():
        print("ERROR: FABRIC_* is not configured in .env — parity check needs live Fabric.")
        return 2
    if not get_postgres_connector().is_configured():
        print("ERROR: PG_REPLICA_* is not configured in .env — parity check needs the live mirror.")
        return 2

    include_counts = not args.skip_rowcount
    print(f"Fetching Fabric metadata for schema {args.schema} (row counts: {include_counts}) ...")
    try:
        fabric_tables = fetch_fabric_table_meta(args.schema, include_row_counts=include_counts)
    except Exception as exc:
        print(f"ERROR: Fabric fetch failed ({type(exc).__name__}): {exc}")
        return 2

    print(f"Fetching Postgres mirror metadata for schema {args.schema} ...")
    try:
        pg_tables = fetch_pg_table_meta(args.schema, include_row_counts=include_counts)
    except Exception as exc:
        print(f"ERROR: Postgres fetch failed ({type(exc).__name__}): {exc}")
        return 2

    report = build_parity_report(fabric_tables, pg_tables)

    print()
    print(f"Tables compared: {report['total']}  |  OK: {report['ok']}  |  "
          f"type-diff only: {report['type_diff_only']}  |  drift: {len(report['drift_tables'])}")
    for name, table in sorted(report["tables"].items()):
        status = table["status"]
        if status == "ok":
            continue
        print(f"\n[{status.upper()}] {args.schema}.{name}")
        cols = table.get("columns") or {}
        for suspect in cols.get("truncation_suspects", []):
            print(f"  - NAMEDATALEN truncation: {suspect['fabric']} -> {suspect['postgres']}")
        for missing in cols.get("missing_in_pg", []):
            print(f"  - missing in Postgres: {missing}")
        for extra in cols.get("extra_in_pg", []):
            print(f"  - extra in Postgres: {extra}")
        for diff in cols.get("type_diffs", []):
            print(f"  - type diff (info): {diff['column']}  fabric={diff['fabric']}  pg={diff['postgres']}")
        rc = table.get("row_count") or {}
        if rc.get("match") is False:
            print(f"  - row count: fabric={rc['fabric']}  pg={rc['postgres']}")

    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON report written to {out}")

    if report["drift"]:
        print("\nRESULT: DRIFT FOUND — mirror is not safe as a fallback until resolved.")
        return 1
    print("\nRESULT: parity OK (type differences, if any, are informational).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
