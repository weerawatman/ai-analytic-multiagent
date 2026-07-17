"""Run golden-question eval and optionally write the G3 gate artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Golden-question eval (Phase G3)")
    parser.add_argument(
        "--harness-baseline",
        action="store_true",
        help="Skip chat/LLM; record empty-answer baseline (for offline gate)",
    )
    parser.add_argument(
        "--write-gate",
        action="store_true",
        help="Write knowledge/.../gates/G3-baseline-recorded.md from this run",
    )
    args = parser.parse_args()

    from backend.app.services.local_paths import ensure_local_structure
    from backend.app.services import eval_service, metric_registry
    from scripts.seed_metric_registry import seed as seed_registry

    ensure_local_structure()
    # Ensure registry + questions exist
    await seed_registry()
    # Copy template questions if missing
    eval_service.load_golden_questions()

    summary = await eval_service.run_eval(harness_baseline=args.harness_baseline)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))

    if args.write_gate:
        repo = Path(__file__).resolve().parents[1]
        gate = repo / "knowledge" / "05-architecture" / "phases" / "gates" / "G3-baseline-recorded.md"
        metrics = metric_registry.load_registry_sync().get("metrics") or []
        approved = sum(1 for m in metrics if m.get("status") == "approved")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        body = f"""# G3 Baseline Recorded

> **วันที่:** {now}
> **run_id:** `{summary["run_id"]}`
> **harness_baseline:** {summary.get("harness_baseline")}
> **source note:** references resolve via Metric Registry + active SQL source when available; harness baseline uses empty answers (accuracy may be 0)

## Metrics

| Metric | Value |
|---|---|
| golden questions | {summary["question_count"]} |
| accuracy_pct | {summary["accuracy_pct"]} |
| sql_success_rate | {summary["sql_success_rate"]} |
| median_latency_s | {summary["median_latency_s"]} |
| registry metrics (approved) | {approved} / {len(metrics)} |

## Result file

`{summary.get("result_path", "")}`

## Notes

- This gate satisfies INV-11 (baseline before Phase H / `backend/app/analytics/`).
- Re-run with live chat pipeline (without `--harness-baseline`) when Ollama is available to refresh numbers — add `G3-baseline-recorded-v2.md` if replacing.
"""
        gate.write_text(body, encoding="utf-8")
        print(f"Wrote gate: {gate}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
