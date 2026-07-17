"""One-shot: build/merge the D-2 numeric overlay entry for CE1SATG.

Reads the D-1 CSV of true-numeric Postgres columns and merges a
SAPHANADB.CE1SATG_All_Cleaned entry into data/local/knowledge/pg_numeric_columns.json,
seeding from the repo template (verified VBRK entry) when the local file
does not exist yet. Column order follows the CSV's ordinal position.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "local" / "exports" / "ce1satg_d1_pg_numeric_columns.csv"
TEMPLATE_PATH = ROOT / "data" / "templates" / "pg_numeric_columns.template.json"
OUT_PATH = ROOT / "data" / "local" / "knowledge" / "pg_numeric_columns.json"
TABLE_KEY = "SAPHANADB.CE1SATG_All_Cleaned"


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows.sort(key=lambda r: int(float(r["pos"])))
    columns = [r["column_name"].strip() for r in rows if r["column_name"].strip()]
    print(f"CSV numeric columns: {len(columns)}")

    if OUT_PATH.exists():
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print("Merging into existing local overlay file")
    else:
        data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        print("Seeding local overlay from template")

    data.setdefault("tables", {})[TABLE_KEY] = columns
    data["verified_note"] = (
        "SAPHANADB.VBRK_All_Cleaned entries verified live against the mirror "
        "(Phase F deep audit). SAPHANADB.CE1SATG_All_Cleaned entries from the "
        "D-1 information_schema analysis of the Postgres mirror (110 true "
        "numeric columns; names are canonical Postgres names). Other tables "
        "pending D-2 confirmation."
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUT_PATH}")

    reloaded = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    entry = reloaded["tables"][TABLE_KEY]
    assert len(entry) == 110, f"expected 110 columns, got {len(entry)}"
    assert all(isinstance(c, str) and c.strip() for c in entry)
    assert "SAPHANADB.VBRK_All_Cleaned" in reloaded["tables"], "VBRK seed lost"
    print("Validation OK: 110 CE1SATG columns, VBRK seed preserved")


if __name__ == "__main__":
    main()
