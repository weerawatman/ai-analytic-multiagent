# Phase J — Learning Loops (สรุปท้าย phase)

**วันที่:** 2026-07-18
**สถานะ:** โค้ด + automated tests เสร็จ; live §9 success criteria ค้าง (cold start — 0 labels จริง)
**เอกสารหลัก:** [phase-j-learning-loops.md](../knowledge/05-architecture/phases/phase-j-learning-loops.md)
**เกต:** [J-done.md](../knowledge/05-architecture/phases/gates/J-done.md)

## สิ่งที่ทำแล้ว

- **sql_error_classifier.py** — แยก classify จาก `data_analyst.py` ให้ `lesson_miner` ใช้ได้โดยไม่ import `app.agents`
- **embedding_service.py** — Ollama `nomic-embed-text` + numpy cosine + SQLite BLOB cache ใน `analytics.db`; hard fallback เป็น truncation
- **Semantic CEO feedback** — `context_nodes` เลือก top-k เมื่อ `embedding_context_enabled=True` (default False)
- **sql_pattern_store.py** — จำ SQL สำเร็จ; กรอง downvote ผ่าน `chat_store.get_downvoted_refs()` (INV-7)
- **lesson_miner.py** + **scripts/mine_lessons.py** — ขุด PDCA → `sql_lessons.json` (ไม่มี job kind ใหม่ — รอ owner)
- **insight_ranker.py** — heuristic เป็นค่าเริ่มต้น; ML + AUC gate offline-tested; wire ใน insight pipeline แบบ no-op เมื่อ dormant
- Deps: scikit-learn / joblib / threadpoolctl; INV-7 ขยาย + sync roadmap
- **Tests:** ~46 เคสใหม่ — ชุดเต็ม **379 passed**

## งานคงเหลือ

- Live: accuracy +10 / retry −30% / ranker AUC จริง (ต้องมี traffic + labels)
- Owner ตัดสินใจ job kind สำหรับ lesson mining
- เปิด embedding / sql-pattern context flags หลัง pull `nomic-embed-text`

## เกตที่ค้าง

- Live §9 metrics (ดู J-done.md)
- Deviation: lesson_miner job kind รอ owner approve

## commits ที่เกี่ยวข้อง

- `08f3af2` — `feat(phase-j): learning loops — embeddings, SQL patterns, lesson miner, insight ranker`
- pushed: 2026-07-18 → origin/master

## หมายเหตุ

- Phase K (`digest_service`, curriculum, `study` job) **ยังไม่เริ่ม** — หยุดตามคำสั่ง
