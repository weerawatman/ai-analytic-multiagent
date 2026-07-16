"""Run quality test prep: health checks + discovery for sales theme."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def get_json(path: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(f"{BASE}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(path: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print("=== Quality Test Prep ===")

    print("1. Backend health...")
    h = get_json("/health", 10)
    print(f"   status: {h.get('status')}")

    print("2. Fabric health...")
    try:
        f = get_json("/api/v1/fabric/health", 120)
        print(f"   fabric: {f.get('status')} connected={f.get('connected')}")
    except Exception as e:
        print(f"   fabric check failed: {e}")

    print("3. Ollama health...")
    try:
        o = get_json("/api/v1/ollama/health", 60)
        print(f"   ollama: {o.get('status')}")
    except Exception as e:
        print(f"   ollama check failed: {e}")

    print("4. Run discovery for theme sales...")
    disc = post_json("/api/v1/discovery/sales/run", 300)
    print(f"   tables_profiled: {disc.get('tables_profiled')}")

    print("5. Verify VBRK columns...")
    discovery = get_json("/api/v1/discovery/sales", 30)
    tables = discovery.get("tables") or discovery.get("profiles") or []
    vbrk = next((t for t in tables if "VBRK" in str(t.get("table", ""))), None)
    if not vbrk:
        print("   VBRK table not found in discovery")
        return 1
    col_names = [c.get("COLUMN_NAME") or c.get("column_name") for c in vbrk.get("columns", [])]
    required = ["Billing_Date", "Net_Value_In_Document_Currency"]
    ok = True
    for c in required:
        if c in col_names:
            print(f"   OK: {c}")
        else:
            print(f"   MISSING: {c}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        print(f"API error: {e}")
        sys.exit(1)
