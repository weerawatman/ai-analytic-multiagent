"""Phase G3 — deterministic eval grading (no LLM judge)."""

from __future__ import annotations

import json

import pytest

from backend.app.services import eval_service, metric_registry


def test_extract_and_grade_numbers():
    nums = eval_service.extract_numbers("ยอดขายรวม 1,234,567.89 บาท และ 100")
    assert 1234567.89 in nums
    assert 100.0 in nums

    q = {"tolerance_pct": 1.0, "expected_keywords_th": ["ไตรมาส"]}
    ok = eval_service.grade_answer(
        q,
        answer_text="ไตรมาสล่าสุดได้ 1000 บาท",
        reference_value=1000.0,
        sql_ok=True,
        latency_s=1.2,
    )
    assert ok["passed"] is True
    assert ok["number_match"] is True

    bad = eval_service.grade_answer(
        q,
        answer_text="ไตรมาสล่าสุดได้ 5000 บาท",
        reference_value=1000.0,
        sql_ok=True,
        latency_s=1.0,
    )
    assert bad["passed"] is False


def test_inv5_eval_service_has_no_llm_imports():
    import ast
    from pathlib import Path

    path = Path(eval_service.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "app.core.llm" not in imports
    assert "anthropic" not in imports
    assert not any(i.startswith("app.core.llm") for i in imports)


@pytest.mark.asyncio
async def test_harness_baseline_writes_result(temp_storage):
    await metric_registry.upsert_metric(
        {
            "metric_key": "metric.revenue_plus_inter",
            "name_th": "รายได้",
            "name_en": "Rev",
            "status": "approved",
            "table": "SAPHANADB.CE1SATG_All_Cleaned",
            "time_column": "SourceMonth",
            "expression": "Revenue",
            "aggregation": "SUM",
        }
    )
    # Seed one golden question locally
    qpath = eval_service.golden_questions_path()
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(
        json.dumps(
            {
                "version": "1.0",
                "questions": [
                    {
                        "id": "gq-test",
                        "question_th": "ยอดขายไตรมาสล่าสุด",
                        "expected_metric_key": "metric.revenue_plus_inter",
                        "reference": {"kind": "metric_registry"},
                        "tolerance_pct": 1.0,
                        "expected_keywords_th": ["ไตรมาส"],
                        "active": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = await eval_service.run_eval(harness_baseline=True, run_id="testbaseline")
    assert summary["question_count"] == 1
    assert summary["harness_baseline"] is True
    assert "accuracy_pct" in summary
    assert (eval_service.results_dir() / "testbaseline.json").exists()


@pytest.mark.asyncio
async def test_eval_api_lists_questions(client, temp_storage):
    # Ensure template is copied
    eval_service.load_golden_questions()
    resp = await client.get("/api/v1/eval/golden-questions")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
