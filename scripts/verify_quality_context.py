"""Verify quality-test context assembly without LLM."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.agents.context_nodes import build_phase2_context
from backend.app.agents.state import AgentState

REQUIRED = ["Billing_Date", "Net_Value_In_Document_Currency"]
FORBIDDEN_IN_SQL_CTX = ["FKDAT", "NETWR"]


def main() -> int:
    state = AgentState(
        thread_id="ctx-check",
        mode="explore",
        theme="ยอดขายและลูกค้า",
        theme_id="sales",
        messages=[],
    )
    ctx = build_phase2_context(state)
    checks: dict[str, bool] = {}
    for col in REQUIRED:
        checks[f"context_has_{col}"] = any(col in v for v in ctx.values())
    sql_ref = ctx.get("sql_reference_context", "")
    checks["sql_reference_loaded"] = "WH_Silver SQL Reference" in sql_ref
    checks["glossary_loaded"] = "Glossary" in ctx.get("knowledge_context", "")
    checks["discovery_loaded"] = "VBRK" in ctx.get("discovery_context", "")

    out = Path("data/local/quality_context_check.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"checks": checks, "context_lengths": {k: len(v) for k, v in ctx.items()}}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(checks))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
