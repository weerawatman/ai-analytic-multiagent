"""Run quality chat test by invoking graph directly (no HTTP timeout)."""

from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage

from backend.app.agents.orchestrator import graph
from backend.app.agents.state import AgentState


def check_quality(content: str) -> dict:
    checks = {
        "uses_billing_date": bool(re.search(r"Billing_Date", content, re.I)),
        "uses_net_value": bool(re.search(r"Net_Value_In_Document_Currency", content, re.I)),
        "has_assumptions": bool(re.search(r"ASSUMPTION", content, re.I)),
        "has_ba_section": bool(
            re.search(r"METRIC_DEFINITION|CEO_QUESTIONS|Business Analyst|BA:", content, re.I)
        ),
        "has_sql": bool(re.search(r"```sql|SELECT", content, re.I)),
    }
    checks["passed"] = (
        checks["uses_billing_date"]
        and checks["uses_net_value"]
        and checks["has_sql"]
    )
    return checks


async def main() -> int:
    thread_id = f"quality-direct-{uuid.uuid4().hex[:8]}"
    message = "ยอดขายในปี 2026 แต่ละเดือน"
    print(f"=== Quality Test Direct: {message} ===")
    print(f"thread: {thread_id}")

    config = {"configurable": {"thread_id": thread_id}}
    input_state = AgentState(
        messages=[HumanMessage(content=message)],
        thread_id=thread_id,
        mode="explore",
        theme="ยอดขายและลูกค้า",
        theme_id="sales",
    )

    try:
        result = await graph.ainvoke(input_state.model_dump(), config=config)
    except Exception as e:
        print(f"Graph failed: {e}")
        return 1

    state = AgentState(**result)
    content = state.final_answer or state.query_result or state.schema_info or ""
    print(f"agent: {state.current_agent}")
    print(f"content length: {len(content)}")

    out_path = Path("data/local/quality_test_last_response.txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Saved to {out_path}")

    checks = check_quality(content)
    check_path = Path("data/local/quality_test_checks.json")
    check_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False))

    preview = content[:2000]
    print("--- preview ---")
    sys.stdout.buffer.write((preview + "\n").encode("utf-8", errors="replace"))

    return 0 if checks.get("passed") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
