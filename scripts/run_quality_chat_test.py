"""Quality test: ask sales 2026 monthly question via the job-based chat API (submit + poll)."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8000"
POLL_INTERVAL_S = 10
MAX_WAIT_S = 3600


def _request(path: str, *, method: str = "GET", payload: dict | None = None, timeout: int = 30) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def submit_chat(message: str) -> str:
    payload = {
        "thread_id": f"quality-test-{uuid.uuid4().hex[:8]}",
        "message": message,
        "mode": "explore",
        "theme": "ยอดขายและลูกค้า",
        "theme_id": "sales",
    }
    result = _request("/api/v1/chat/", method="POST", payload=payload)
    return result["job_id"]


def poll_job(job_id: str) -> dict:
    """Poll the job, printing each step transition, until it reaches a terminal state."""
    deadline = time.time() + MAX_WAIT_S
    last_step = None
    while time.time() < deadline:
        job = _request(f"/api/v1/jobs/{job_id}")
        status = job.get("status")
        step = job.get("current_step")
        if step != last_step and step:
            print(f"  [{time.strftime('%H:%M:%S')}] current step: {step}")
            last_step = step
        if status not in ("queued", "running"):
            return job
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"Job {job_id} did not finish within {MAX_WAIT_S}s")


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
    print("=== Quality Test: ยอดขาย 2026 รายเดือน (job-based) ===")
    try:
        job_id = submit_chat("ยอดขายในปี 2026 แต่ละเดือน")
        print(f"job submitted: {job_id}")
        job = poll_job(job_id)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Chat failed: {e.code} {body}")
        return 1
    except Exception as e:
        print(f"Chat failed: {e}")
        return 1

    if job.get("status") != "done":
        print(f"Job ended with status={job.get('status')} error={job.get('error')}")
        print("--- step timeline ---")
        for p in job.get("progress", []):
            print(f"  {p.get('step')}: {p.get('status')} {p.get('note') or ''}")
        return 1

    result = job.get("result") or {}
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
