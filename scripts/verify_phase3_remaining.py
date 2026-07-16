"""Phase 3 remaining verification — API-level smokes (no Fabric required).

Usage:
  $env:PYTHONPATH="."; .\\.venv\\Scripts\\python.exe scripts\\verify_phase3_remaining.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = "http://127.0.0.1:8000"
THEME = "sales"


def _ok(msg: str) -> None:
    print(f"OK  {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL {msg}")
    sys.exit(1)


def check_status_enabled(client: httpx.Client) -> None:
    r = client.get(f"{BACKEND}/api/v1/consultant/status")
    r.raise_for_status()
    data = r.json()
    if not data.get("enabled"):
        _fail("consultant status.enabled is false — set CONSULTANT_ENABLED + API key")
    _ok(f"consultant enabled model={data.get('model')}")


def check_discovery_and_memory(client: httpx.Client) -> None:
    d = client.get(f"{BACKEND}/api/v1/discovery/{THEME}")
    if d.status_code != 200:
        _fail(f"discovery/{THEME} missing — need disk cache for offline Explore")
    _ok(f"discovery/{THEME} profiles={len(d.json().get('profiles') or [])}")

    m = client.get(f"{BACKEND}/api/v1/onboarding/{THEME}")
    if m.status_code != 200:
        _fail(f"team memory/{THEME} missing")
    mem = m.json()
    notes = mem.get("consultant_notes") or []
    _ok(f"team memory status={mem.get('status')} consultant_notes={len(notes)}")


def check_consult_job(client: httpx.Client) -> None:
    r = client.post(
        f"{BACKEND}/api/v1/consultant/{THEME}/consult",
        json={"question": "สรุปสั้น ๆ ว่าทีมควรยืนยันนิยามยอดขายอย่างไร (verify smoke)"},
        timeout=30,
    )
    if r.status_code == 409:
        job_id = r.json()["detail"]["job_id"]
        _ok(f"consult already running job={job_id}")
    else:
        r.raise_for_status()
        job_id = r.json()["job_id"]
        _ok(f"consult submitted job={job_id}")

    deadline = time.time() + 300
    while time.time() < deadline:
        job = client.get(f"{BACKEND}/api/v1/jobs/{job_id}", timeout=30).json()
        if job["status"] not in ("queued", "running"):
            if job["status"] != "done":
                _fail(f"consult job {job['status']}: {job.get('error')}")
            advice = (job.get("result") or {}).get("advice") or ""
            if len(advice) < 20:
                _fail("consult advice too short")
            _ok(f"consult done advice_chars={len(advice)}")
            return
        time.sleep(5)
    _fail("consult job timeout")


def check_audit_security() -> None:
    path = ROOT / "data" / "local" / "logs" / "consultant_audit.jsonl"
    if not path.exists():
        _fail("consultant_audit.jsonl missing")
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    rec = json.loads(line)
    payload = rec.get("payload") or ""
    for bad in ("QUERY_RESULT", "SQL_RESULT", "sample_preview", "sample_rows"):
        if bad in payload:
            _fail(f"audit payload contains {bad}")
    if rec.get("status") != "ok":
        _fail(f"latest audit status={rec.get('status')} error={rec.get('error')}")
    _ok(f"audit SECURITY_OK mode={rec.get('mode')} chars={rec.get('payload_chars')}")


async def run_coach() -> None:
    from backend.app.core.config import get_settings
    from backend.app.services import consultant_service

    get_settings.cache_clear()
    if not consultant_service.is_enabled("coach_onboarding"):
        _fail("coach_onboarding disabled")
    coach = await consultant_service.coach_team(THEME, "ยอดขาย")
    if not coach:
        _fail("coach_team returned None")
    roles = (coach.get("role_coaching") or {}).keys()
    _ok(f"coach_team roles={list(roles)} glossary={len(coach.get('glossary_proposals') or [])}")


def submit_and_poll_chat_job(client: httpx.Client, timeout_sec: int = 3600) -> None:
    thread = f"verify-p3-{int(time.time()) % 100000}"
    r = client.post(
        f"{BACKEND}/api/v1/chat/",
        json={
            "thread_id": thread,
            "message": "สรุปสั้น ๆ จาก discovery ว่าตารางยอดขายหลักคืออะไร (ไม่ต้องรัน SQL จริง)",
            "mode": "explore",
            "theme": "ยอดขาย",
            "theme_id": THEME,
        },
        timeout=30,
    )
    r.raise_for_status()
    job_id = r.json()["job_id"]
    _ok(f"chat job submitted thread={thread} job={job_id}")
    print(f"CHAT_JOB_ID={job_id}")
    print(f"CHAT_THREAD={thread}")

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        job = client.get(f"{BACKEND}/api/v1/jobs/{job_id}", timeout=30).json()
        status = job["status"]
        step = job.get("current_step")
        print(f"  chat status={status} step={step}", flush=True)
        if status not in ("queued", "running"):
            steps = {p["step"]: p["status"] for p in (job.get("progress") or [])}
            content = (job.get("result") or {}).get("content") or ""
            if status != "done":
                _fail(f"chat job {status}: {job.get('error')}")
            if steps.get("consultant_review") != "done":
                _fail(f"consultant_review not done: {steps}")
            if "Claude" not in content and "ที่ปรึกษา" not in content:
                _fail("chat result missing consultant section")
            failed_agents = [k for k, v in steps.items() if v == "failed" and k != "consultant_review"]
            if failed_agents:
                print(f"WARN agent steps failed (OOM/LLM): {failed_agents}")
            else:
                _ok("all local agent steps done")
            _ok(f"chat+consultant_review done content_chars={len(content)}")
            return
        time.sleep(15)
    _fail("chat job timeout")


def main() -> None:
    with httpx.Client(timeout=60) as client:
        h = client.get(f"{BACKEND}/health")
        h.raise_for_status()
        _ok("backend health")
        check_status_enabled(client)
        check_discovery_and_memory(client)
        check_consult_job(client)
        check_audit_security()
        mem = client.get(f"{BACKEND}/api/v1/onboarding/{THEME}").json()
        notes = mem.get("consultant_notes") or []
        if not notes:
            _fail("consultant_notes empty after consult — Team Memory panel would be empty")
        _ok(f"team memory has consultant_notes={len(notes)}")

    asyncio.run(run_coach())
    with httpx.Client(timeout=60) as client:
        # Allow override for quick smoke vs full wait
        import os

        timeout = int(os.getenv("VERIFY_CHAT_TIMEOUT", "3600"))
        submit_and_poll_chat_job(client, timeout_sec=timeout)
    print("VERIFY_PHASE3_REMAINING_OK")


if __name__ == "__main__":
    main()
