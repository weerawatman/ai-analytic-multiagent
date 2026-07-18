# Phase J Done

> **วันที่:** 2026-07-18
> **commit hash:** N/A (working tree — owner will commit; base Phase I `2525108` + custom subagent team `2477b32`)
> **phase doc:** [phase-j-learning-loops.md](../phase-j-learning-loops.md)
> **precondition:** Phase G1b (`answer_ratings`) + Phase I (`insight_feedback` / feed) — cold start จริง (0 labels)

## เกณฑ์สำเร็จ Phase J (roadmap §9)

| เกณฑ์ | สถานะ | หลักฐาน |
|---|---|---|
| Golden-question accuracy **+≥ 10 จุด** จาก baseline | ⏳ pending live | วงจรเรียนรู้พร้อม (SQL patterns + lessons + semantic feedback) แต่ยังไม่มี labels/PDCA จริงพอวัดเทียบ baseline — ไม่ invent ตัวเลข |
| SQL retry ต่อคำถามลดลง ≥ 30% (วัดจาก PDCA log) | ⏳ pending live | `lesson_miner` + `scripts/mine_lessons.py` พร้อม; `pdca_failures.jsonl` ยังว่าง/ไม่มี — วัดไม่ได้จนกว่าจะมี traffic จริง |
| Ranker AUC ≥ 0.65 เมื่อ trained; useful% ใน top-5 ของ feed ดีขึ้น MoM | ⏳ pending live / ✅ offline | Offline: synthetic 120 labels ผ่าน AUC gate ≥ 0.6 และ promote model (`test_insight_ranker.py`); live: 0/100 labels จริง → ML dormant, heuristic active (ตาม locked decision) |

## pytest

```
379 passed in ~90s
```

(Step 12 sanity ก่อนเทสต์ใหม่: `1 failed, 332 passed` — INV-7 docstring เท่านั้น; แก้แล้ว)

Conformance (`test_roadmap_conformance.py`): INV-1..INV-9, INV-11 **pass**; INV-8 เปลี่ยนจาก skip → pass รอบนี้

## สิ่งที่ส่งมอบ (โค้ด)

- `sql_error_classifier.py` — pure classifier แยกจาก `data_analyst.py`
- `embedding_service.py` + `make_embed_ollama()` + config `ollama_embed_model` / `embedding_context_enabled`
- Semantic CEO feedback retrieval ใน `context_nodes.py` / `feedback_store.format_feedback_entries`
- `sql_pattern_store.py` + `chat_store.get_downvoted_refs()` + DA wire (`sql_pattern_context_enabled`)
- `lesson_miner.py` + `scripts/mine_lessons.py` + DA `sql_lessons_in_prompt` (default True)
- `insight_ranker.py` (`MIN_LABELS_FOR_ML=100`, `MIN_AUC_GATE=0.6`) + wire ใน `insight_pipeline._score_candidates`
- Deps: `scikit-learn==1.9.0`, `joblib`, `threadpoolctl`
- INV-7 ขยายครอบ 4 services ใหม่ + sync roadmap §4.1
- Tests: `test_sql_error_classifier`, `test_embedding_service`, `test_sql_pattern_store`, `test_lesson_miner`, `test_insight_ranker`, `test_feedback_semantic_context`

## Manual / human gates ที่ยังค้าง

1. Owner approve Deviation Log: เพิ่ม job kind สำหรับ lesson mining หรือคง script-only
2. สะสม `answer_ratings` / `insight_feedback` ≥ 100 labels แล้ว retrain ranker จริง
3. เปิด `EMBEDDING_CONTEXT_ENABLED` / `SQL_PATTERN_CONTEXT_ENABLED` หลังมี Ollama `nomic-embed-text`
4. รัน golden-eval เทียบ baseline หลังมี traffic จริง (วัด accuracy +10 / retry −30%)
5. Owner commit + push (agent ไม่ commit ตามคำสั่ง)
6. **อย่าเริ่ม Phase K จนกว่า owner จะสั่ง**
