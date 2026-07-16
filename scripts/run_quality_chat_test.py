"""Quality test: ask sales 2026 monthly question via chat API."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"


def post_chat(message: str, timeout: int = 1800) -> dict:
    payload = {
        "thread_id": f"quality-test-{uuid.uuid4().hex[:8]}",
        "message": message,
        "mode": "explore",
        "theme": "ยอดขายและลูกค้า",
        "theme_id": "sales",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/v1/chat/",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_quality(content: str) -> dict:
    checks = {
        "uses_billing_date": bool(re.search(r"Billing_Date", content, re.I)),
        "uses_net_value": bool(re.search(r"Net_Value_In_Document_Currency", content, re.I)),
        "avoids_fkdat": "FKDAT" not in content.upper() or "SAP FKDAT" in content,
        "avoids_netwr": "NETWR" not in content.upper() or "SAP NETWR" in content,
        "has_assumptions": bool(re.search(r"ASSUMPTION", content, re.I)),
        "has_ba_section": bool(re.search(r"METRIC_DEFINITION|CEO_QUESTIONS|Business Analyst|BA:", content, re.I)),
        "has_sql": bool(re.search(r"```sql|SELECT", content, re.I)),
    }
    checks["passed"] = (
        checks["uses_billing_date"]
        and checks["uses_net_value"]
        and checks["has_sql"]
    )
    return checks


def main() -> int:
    print("=== Quality Test: ยอดขาย 2026 รายเดือน ===")
    try:
        result = post_chat("ยอดขายในปี 2026 แต่ละเดือน")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Chat failed: {e.code} {body}")
        return 1
    except Exception as e:
        print(f"Chat failed: {e}")
        return 1

    content = result.get("content", "")
    agent = result.get("agent", "")
    print(f"agent: {agent}")
    print(f"content length: {len(content)}")
    print("--- response preview (first 3000 chars) ---")
    print(content[:3000])
    print("--- end preview ---")

    checks = check_quality(content)
    print("Quality checks:")
    for k, v in checks.items():
        print(f"  {k}: {v}")

    out_path = "data/local/quality_test_last_response.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Full response saved to {out_path}")

    return 0 if checks.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
