# Phase G→K — Grand Roadmap: Self-Learning Analytics (จาก LLM Orchestration สู่ระบบวิเคราะห์ที่เรียนรู้เองได้)

> **สถานะ:** เอกสารแผน (approved โดย owner, ยังไม่เริ่ม implement) — เขียนขึ้นจาก feedback ว่า "ระบบยังไปไม่ถึง machine learning" และวิสัยทัศน์ของ owner: ระบบวิเคราะห์ insight ระดับโลกแนว **Google Analytics Insights (BigQuery)** — proactive (วิเคราะห์เองโดยไม่ต้องรอคำถาม), เรียนรู้จากข้อมูลใน Postgres mirror ได้ต่อเนื่องโดยไม่ต้องรอ Fabric, เก่งขึ้นเรื่อยๆ แบบวัดผลได้, รับ feedback มาพัฒนาตัวเอง, agents ทำหน้าที่เหมือนมืออาชีพระดับ PhD + ประสบการณ์ 20 ปี ที่รู้คำถามพื้นฐานของ role ตัวเองโดยไม่ต้องรอใครสั่ง
> **ผู้ดำเนินการ:** ทีมพัฒนา (ทีละ phase, ไม่เร่งรีบแต่ต้องจับต้องได้ทุก phase) — แต่ละ phase เมื่อเริ่มจริงให้สร้าง doc แยกตาม convention เดิม (`phase-g-foundation.md` ฯลฯ)
> **การปิดบัญชีตัวอักษร phase:** Phase C เดิม (automated homework scheduler — พักไว้ตั้งแต่ phase-d) ถูก **absorb เข้า Phase K** (role curriculum + `study` job), Phase E เดิม (sandboxed Python execution) เป็น **optional ใน Phase K** — ตัวอักษรถัดไปที่ว่างจึงเป็น G และ roadmap นี้จอง G, H, I, J, K
> **การกำกับทิศทาง (เพิ่ม 2026-07-18):** การ implement ทุก phase อยู่ใต้ **§4 Delegation Guardrails** — invariants ถูกบังคับอัตโนมัติด้วย conformance tests ([backend/tests/test_roadmap_conformance.py](../../../backend/tests/test_roadmap_conformance.py)) ที่รันรวมกับ pytest ชุดปกติ, phase doc ต้องสร้างจาก [_TEMPLATE-phase.md](_TEMPLATE-phase.md) ก่อนเขียนโค้ด, และจบ phase ต้องมี gate artifact ใน [gates/](gates/)

---

## 1. Gap Analysis — ระบบวันนี้ vs วิสัยทัศน์

### สิ่งที่มีแล้ว (ของดีที่ต้องต่อยอด ไม่ทิ้ง)
- Multi-agent graph DE→DS→DA→BA→Quality บน LangGraph + Ollama, Claude เป็น consultant ภายนอก ([orchestrator.py](../../../backend/app/agents/orchestrator.py))
- Data layer 2 ชั้นพร้อม provenance: Fabric WH_Silver → Postgres mirror auto-fallback, dialect ตัดสินก่อน generate SQL, read-only guard, row-count guard (Phase D+F)
- Team memory ต่อ theme, knowledge store (glossary/targets/relationships) แบบ draft→approved HITL, deep profile "homework" (deterministic), insight starter pack, briefings
- Job runner + progress timeline + orphan reconciliation ([job_runner.py](../../../backend/app/services/job_runner.py), [job_store.py](../../../backend/app/services/job_store.py))

### ช่องว่างจริง (ยืนยันจากการ audit โค้ดทั้ง repo, 2026-07-18)
| # | ช่องว่าง | หลักฐาน |
|---|---|---|
| 1 | **ไม่มี ML/สถิติจริงแม้แต่บรรทัดเดียว** | ไม่มี import pandas/numpy/scipy/statsmodels/sklearn ใน app code เลย, `requirements.txt` ไม่มีสัก lib — คำว่า "outlier/2SD/Pareto" ทั้งหมดเป็นแค่ prompt text ให้ LLM ไม่ใช่การคำนวณ |
| 2 | **ไม่มี scheduler ใดๆ** | ทุกฟีเจอร์ "proactive" (homework, starter pack, briefing) ต้องรอคนกดปุ่ม — ไม่มี cron/APScheduler/Task Scheduler |
| 3 | **ไม่มีเครื่องวัดว่าเก่งขึ้น** | ไม่มี golden questions / eval harness / accuracy tracking — Quality Bar D เช็คแค่ "คำตอบมีครบทุกช่อง" ไม่ใช่ "คำตอบถูก" |
| 4 | **Feedback loop ขาดครึ่ง** | PDCA failure log เขียนแล้วไม่มีใครอ่าน (write-only), chat ไม่มีปุ่มให้คะแนนคำตอบ, SQL ที่สำเร็จไม่ถูกเก็บเป็น pattern ให้เรียนรู้ |
| 5 | **Retrieval เป็น char-budget truncation** | knowledge เข้า prompt แบบตัดตามงบตัวอักษร ไม่ใช่ semantic — ยิ่ง KB โต ยิ่ง recall แย่ |
| 6 | **UX ตอนรอ ดูไม่ออกว่าทำงานอยู่หรือตาย** | poll ทุก 3 วิ แต่ระหว่าง Ollama คิดนานๆ ไม่มีอะไรขยับ — backend ตาย vs node ช้า แยกไม่ออก |

**สรุปทิศทาง:** ไม่ต้องรื้อของเดิม — เติม 5 ชิ้นที่ขาด: (1) สมองสถิติจริง (2) นาฬิกาปลุกให้ทำงานเอง (3) เครื่องวัดความเก่ง (4) วงจรเรียนรู้จาก feedback (5) UX ที่มองเห็นชีพจรระบบ

---

## 2. หลักการใหญ่ 3 ข้อ (ใช้บังคับทุก phase)

1. **Evidence-first — LLM ไม่เคยคำนวณตัวเลขเอง**: สถิติ/ตัวเลขทุกตัวคำนวณด้วย Python (pandas/scipy) จาก SQL ที่ render แบบ deterministic — LLM ทำหน้าที่เดียวคือ **เล่าเรื่อง (narrate) จาก evidence JSON** และมี numeric validator ตรวจว่าเลขทุกตัวใน narrative ต้องปรากฏใน evidence (mismatch → re-narrate 1 ครั้ง → fallback template) นี่คือกำแพงกัน hallucination ที่ทำให้ insight เชื่อถือได้ระดับ production
2. **วัดผลได้ตั้งแต่วันแรก**: "วันแรกยังตอบไม่ถูกก็ได้ แต่ต้องเก่งขึ้นเรื่อยๆ" พิสูจน์ได้ทางเดียวคือมี baseline — golden-question eval ต้องรันและบันทึกผล **ก่อน** Phase H/I/J เริ่ม แล้ววัดซ้ำทุก phase เทียบกับเลขนั้น
3. **ใช้โครงเดิมให้สุด**: งาน scheduled ทุกชนิดวิ่งผ่าน `job_runner`/`job_store` เดิม (ได้ progress timeline, orphan reconciliation, wall-clock cap, heartbeat ฟรี) — และ SQL ทุก query ที่รันแบบอัตโนมัติต้อง render จาก Metric Registry แบบ deterministic **ห้ามพึ่ง LLM discipline ใน path ที่ไม่มีคนดู**

---

## 3. การตัดสินใจที่ล็อกแล้ว (ห้ามเปลี่ยนโดยไม่ถาม owner)

| หัวข้อ | ตัดสินใจ |
|---|---|
| Stats stack | `pandas` + `numpy` + `scipy` เป็น core (required); `statsmodels` เป็น optional แบบ import-guarded (STL/ETS เป็นของแถม ไม่ใช่ dependency บังคับ); **ไม่ใช้ prophet** — Python venv คือ 3.14.2 บน Windows, task 0 ของ Phase H คือ verify cp314 wheels ก่อน commit dependency |
| Snapshot grain | **1-D slices เท่านั้น**: `month × {__total__, Customer, Product_Number(top-500 + __other__), Profit_Center, Sales_Organization, Material_Group_MATKL}` — **ไม่ทำ cube 2 มิติ** (CE1SATG 1.6M rows, ~38k products จะระเบิด; contribution analysis แบบ GA ใช้แค่ 2 periods × 1 dimension คำนวณสดจาก mirror ได้) |
| Storage ใหม่ | SQLite แยกไฟล์ `data/local/analytics/analytics.db` (WAL mode) — ไม่แตะ `app.db` ที่โดน UI poll ทุก 3 วิ |
| Scheduler | APScheduler (`AsyncIOScheduler`) ใน FastAPI lifespan — **catch-up-on-startup เป็นกลไกหลัก** (backend รัน manual: ถ้ารอบสำเร็จล่าสุดเก่ากว่า `insight_catchup_after_hours` (default 24) → enqueue หลัง start 120 วิ), nightly cron 02:00 เป็นโบนัส, **defer เสมอเมื่อมี chat/onboarding job active** (Ollama instance เดียว) + มีปุ่ม "รันเดี๋ยวนี้" ใน UI |
| แหล่งข้อมูลการเรียนรู้ | ใช้ source resolution เดิมของ Phase F (Fabric ก่อน → Postgres mirror → offline) + provenance label ทุกชิ้นงานเสมอ — เจตนาออกแบบคือ pipeline เรียนรู้จาก **mirror ได้ต่อเนื่องโดยไม่ต้องรอ Fabric** (ตอบโจทย์ "postgres มีข้อมูลเท่า WH_Silver ไม่ต้องรอ fabric") |
| Embedding | Ollama `nomic-embed-text` (~274MB, ไหวบน CPU) + cosine similarity ด้วย numpy บน SQLite BLOB — **ไม่มี vector DB** ในขอบเขตนี้ |
| Grading ของ eval | Deterministic เท่านั้น (เทียบตัวเลข ± tolerance กับค่าอ้างอิงที่ render จาก registry บน source เดียวกัน) — **ไม่ใช้ LLM-judge** |
| Insight ranker | Heuristic score จนกว่าจะมี labels ≥ 100 → ค่อยสลับเป็น logistic regression และต้องผ่าน holdout AUC ≥ 0.6 เท่านั้น (ไม่ผ่าน = ใช้ heuristic ต่อ + log ไว้ ไม่ silent) |

---

## 4. Delegation Guardrails — กติกาบังคับเมื่อมอบหมายให้ AI ทำต่อ

> Roadmap นี้ออกแบบให้ **AI session อื่นรับไป implement ต่อได้โดยทิศทางไม่เพี้ยน** และผู้ตรวจ (owner หรือ AI reviewer) ตรวจย้อนหลังได้โดยไม่ต้องเชื่อคำรายงานของผู้ทำ — กลไกมี 2 ชั้น: (1) **conformance tests** ที่ [backend/tests/test_roadmap_conformance.py](../../../backend/tests/test_roadmap_conformance.py) รันรวมกับ pytest ชุดปกติ — invariant ของ module ที่ยังไม่ถูกสร้างจะ skip และ**เริ่มบังคับทันทีที่ module นั้นเกิดขึ้น** (2) **ร่องรอยใน git** — phase doc จาก template + Deviation Log + gate artifacts ใน `gates/`

### 4.1 Invariants (INV-1..INV-12)

`[AUTO]` = มี conformance test คุมอัตโนมัติ / `[REVIEW]` = ผู้ตรวจดูเองตาม checklist §4.5

| # | ป้าย | Invariant |
|---|---|---|
| INV-1 | `[AUTO]` | `backend/requirements.txt` ห้ามมี dependency ต้องห้าม: `prophet`, `chromadb`, `faiss`, `qdrant`, `weaviate`, `pgvector`, `redis`, `celery` (ไม่มี vector DB / message queue / forecasting lib ที่ build ยากบน Windows) |
| INV-2 | `[AUTO]` | ทุกไฟล์ใน `backend/app/analytics/` ต้อง **pure** — ห้าม import httpx/requests/langchain*/langgraph/ollama/anthropic/psycopg2/pyodbc/sqlite3/sqlalchemy/fastapi/streamlit/app.services/app.agents/app.api — สถิติต้อง unit-test offline ได้ 100% |
| INV-3 | `[AUTO]` | `snapshot_refresh_service.py` ต้องใช้ `render_metric_sql` จาก `metric_registry` และห้ามแตะ `make_chat_ollama` — **SQL ใน scheduled path มาจาก registry เท่านั้น ไม่พึ่ง LLM** |
| INV-4 | `[AUTO]` | `insight_pipeline.py` ต้องเรียก `validate_narrative_numbers` — narrative ทุกชิ้นผ่าน numeric validator (หลักการใหญ่ข้อ 1) |
| INV-5 | `[AUTO]` | `eval_service.py` ห้าม import `app.core.llm` / `anthropic` — grading เป็น deterministic, **LLM เป็นผู้ถูกสอบ ไม่ใช่ผู้ให้คะแนน** |
| INV-6 | `[AUTO]` | `scheduler_service.py` ต้อง enqueue งานผ่าน `job_runner` และห้าม import threading/multiprocessing/subprocess — **ไม่มี execution path คู่ขนานนอก job runner** |
| INV-7 | `[AUTO]` | services กลุ่ม analytics (`snapshot_store`, `snapshot_refresh_service`, `insight_store`, `insight_pipeline`, `scheduler_service`, `embedding_service`, `sql_pattern_store`, `lesson_miner`, `insight_ranker` — 4 รายการหลังเพิ่มใน Phase J) ห้ามมี string `app.db` — เขียนเฉพาะ `analytics.db`; การอ่านข้อมูล `answer_ratings` (เช่น กรอง "ไม่เคยโดน 👎" ใน `sql_pattern_store`) ต้องผ่าน read-only helper ที่ `chat_store.py` เปิดให้ (เช่น `get_downvoted_refs()`) ไม่ใช่เปิด connection ตรงไปที่ `app.db` เอง |
| INV-8 | `[AUTO]`+`[REVIEW]` | `insight_ranker.py` ต้องประกาศ `MIN_LABELS_FOR_ML = 100` และ `MIN_AUC_GATE = 0.6` `[AUTO]`; การสลับ heuristic→ML และผล AUC ทุกรอบ retrain ต้องถูก log เสมอ ห้ามสลับเงียบ `[REVIEW]` |
| INV-9 | `[AUTO]` | services ใหม่ทุกตัวของ roadmap นี้ห้าม import `psycopg2`/`pyodbc` ตรง — SQL ทุก path ผ่าน `run_sql`/`run_sql_async` ของ `fabric_sql.py` เพื่อให้ sql_guard + row-count guard + provenance ทำงานเสมอ |
| INV-10 | `[REVIEW]` | ทุก insight/คำตอบติด provenance label (🟦 fabric / 🟨 postgres / ⚪ offline) — สอดคล้อง Phase F ไม่มี fallback เงียบ |
| INV-11 | `[AUTO]` | **Baseline gate:** ถ้า `backend/app/analytics/` ถูกสร้างแล้ว ต้องมีไฟล์ [gates/G3-baseline-recorded.md](gates/) ใน git — **ห้ามเริ่มสร้างสมองสถิติ (Phase H) ก่อนบันทึกไม้บรรทัด (G3)** เพราะ `data/local/` ไม่อยู่ใน git ผล baseline จึงต้องถูกคัดลอกมาเก็บเป็น gate artifact |
| INV-12 | `[REVIEW]` | ห้ามเพิ่ม framework/infra ใหม่ (Redis/Celery/vector DB/Docker — ยกเว้น sandbox ใน Phase K ตาม locked decision ของ phase-d), Streamlit ห้ามเพิ่ม fragment poll ตัวใหม่ (feed ใช้ `st.cache_data`) |

### 4.2 Canonical Names Freeze — ชื่อที่ล็อกแล้ว

เปลี่ยนชื่อใดๆ ในตารางนี้ = ต้อง owner approve + แก้ roadmap นี้ + แก้ conformance test **ใน commit เดียวกัน** (ไม่เช่นนั้น AI คนละ session จะเขียนโค้ดเข้ากันไม่ได้ และเทสต์จะตรวจไม่เจอ)

| หมวด | ชื่อ canonical |
|---|---|
| Analytics modules (pure) | `backend/app/analytics/detectors.py`, `contribution.py`, `forecasting.py` |
| Services ใหม่ | `backend/app/services/` → `metric_registry.py`, `progress_reporter.py`, `eval_service.py`, `snapshot_store.py`, `snapshot_refresh_service.py`, `insight_store.py`, `insight_pipeline.py`, `scheduler_service.py`, `embedding_service.py`, `sql_pattern_store.py`, `lesson_miner.py`, `insight_ranker.py`, `digest_service.py` |
| Routes ใหม่ | `backend/app/api/routes/` → `metrics.py`, `ratings.py`, `analytics.py`, `insights.py`, `eval.py` |
| Functions | `render_metric_sql(entry, source, *, months, dimension)` (metric_registry), `validate_narrative_numbers(narrative_th, evidence)` (insight_pipeline), `touch_job(job_id)` (job_store), `note_substep(thread_id, text)` (progress_reporter) |
| Job kinds | `snapshot_refresh`, `insight_pipeline`, `study` (ผ่าน job_runner เท่านั้น) |
| SQLite ใหม่ | `data/local/analytics/analytics.db` (WAL) — ตาราง `metric_snapshots` (PK: metric_key, period, dim_name, dim_value), `snapshot_runs`, `insights`, `insight_feedback`, `sql_patterns`; ส่วน `answer_ratings` อยู่ใน `app.db` (chat store เดิม) |
| Store files | `data/local/knowledge/metric_registry.json`, `data/local/knowledge/sql_lessons.json`, `data/local/eval/golden_questions.json`, `data/local/eval/results/`, `data/local/models/insight_ranker.pkl`, `data/local/knowledge/curriculum/{role}.json`, `data/local/briefings/digests/` |
| Config keys | `insight_pipeline_enabled`, `insight_cron_hour`, `insight_narrate_top_k`, `insight_catchup_after_hours`, `ollama_embed_model` |
| Constants | `MIN_LABELS_FOR_ML = 100`, `MIN_AUC_GATE = 0.6` (insight_ranker) |

### 4.3 Phase Gates — หลักฐานจบ phase เก็บใน git

จบแต่ละ phase ต้องสร้าง gate artifact ใน [gates/](gates/) (กติกาละเอียดใน `gates/README.md`):

| ไฟล์ gate | สร้างเมื่อ | เนื้อหาขั้นต่ำ |
|---|---|---|
| `G3-baseline-recorded.md` | จบ G3 **ก่อนเริ่ม H** (INV-11 บังคับ) | วันที่, จำนวน golden questions, `accuracy_pct` / `sql_success_rate` / `median_latency_s` baseline, commit hash |
| `G-done.md`, `H-done.md`, `I-done.md`, `J-done.md`, `K-done.md` | จบ phase นั้นๆ | checklist เกณฑ์สำเร็จของ phase (จาก §6–§10) พร้อมหลักฐานจริงต่อข้อ + ผล pytest + commit hash |

### 4.4 Handoff Protocol — ขั้นตอนบังคับสำหรับ AI ผู้รับงาน

1. อ่าน [AGENTS.md](../../../AGENTS.md) + §4 นี้ทั้งหมด ก่อนเริ่มงานทุกครั้ง
2. สร้าง phase doc จาก [_TEMPLATE-phase.md](_TEMPLATE-phase.md) **ก่อนเขียนโค้ดบรรทัดแรก** — กรอก scope in/out ให้ชัด
3. ทำเฉพาะ scope ของ phase ที่ได้รับมอบ — งานนอก scope ให้จดเป็นข้อเสนอใน phase doc ไม่ใช่ทำเลย
4. จำเป็นต้องเบี่ยงจาก locked decisions (§3) / canonical names (§4.2) → **หยุด บันทึกใน Deviation Log แล้วถาม owner ก่อน** — ห้าม "ทำไปก่อนค่อยบอก"
5. ก่อนจบงาน: รัน pytest เต็มชุด (conformance tests รวมอยู่แล้ว) — ต้องเขียวทั้งหมด ห้าม skip/xfail เทสต์เดิมเพื่อให้ผ่าน
6. กรอก DoD checklist + Deviation Log + commit summary ใน phase doc แล้วจึงถือว่างานส่งมอบได้

### 4.5 Reviewer Checklist — สำหรับ owner/ผู้ตรวจย้อนหลัง

```powershell
# รันจาก repo root เสมอ (conftest ต้องการ)
.\.venv\Scripts\python.exe -m pytest backend/tests -q                              # ทั้งชุดต้องเขียว
.\.venv\Scripts\python.exe -m pytest backend/tests/test_roadmap_conformance.py -v  # ดู invariant รายข้อ: pass/skip ต้องตรงสถานะ phase จริง
```
จากนั้น: เปิด phase doc ของงานที่ถูกมอบหมาย → ตรวจ DoD checklist กรอกจริงไหม → **Deviation Log ว่างหรือทุกแถวมี owner approve** → ดู `gates/` ว่า phase ที่อ้างว่าจบมี gate artifact + หลักฐาน → `git log --oneline` เทียบกับ scope ใน phase doc ว่าไม่มี commit แปลกปลอม → สุ่มตรวจ `[REVIEW]` invariants (INV-10, INV-12, INV-8 ส่วน log)

---

## 5. คำถามที่ owner ต้องตอบก่อนเริ่ม G2 (open items)

| # | คำถาม | ทำไมต้องรู้ |
|---|---|---|
| O-1 | **สูตร Net Profit ที่ถูกต้อง** — ใช้คอลัมน์ไหนบ้างใน `CE1SATG_All_Cleaned` (Selling_Expense, Admin_Expense, …, Income_Tax?) | seed `metric.net_profit` ได้แค่ draft จนกว่าจะยืนยัน |
| O-2 | **นิยาม discount rate ต่อลูกค้า** — คอลัมน์ candidate: `Price_Adjustment` / `Price_Adjustment_RM` ใช่หรือไม่ ฐานหารคืออะไร | seed `metric.discount_rate` ได้แค่ draft |
| O-3 | **ฐานเวลา canonical สำหรับ QoQ/YoY** — ใช้ `SourceMonth` (YYYYMM, calendar quarter) หรือ `Fiscal_Year`/`Period` (fiscal quarter)? | กระทบทุก metric แบบ period_delta และ golden questions ทั้งชุด |

---

## 6. Phase G — Foundation: มองเห็น, มีมาตรฐาน, มีไม้บรรทัด (Effort M, ~2–3 สัปดาห์)

> เป้าหมาย: แก้ pain UX ที่ owner เจอทุกวัน + สร้าง 2 โครงสร้างพื้นฐานที่ทุก phase หลังยืนอยู่บนมัน (Metric Registry + Eval) + เริ่มสะสม feedback labels ตั้งแต่วันแรก

### G1 — Heartbeat UX: แยก "ทำงานอยู่" ออกจาก "ตาย/error" ให้ได้ทุกกรณี
- [job_store.py](../../../backend/app/services/job_store.py): เพิ่มคอลัมน์ `heartbeat_at` (idempotent migration ใน `init_jobs_db`) + ฟังก์ชัน `touch_job(job_id)`
- [job_runner.py](../../../backend/app/services/job_runner.py): asyncio ticker ต่อ job (ทุก ~10 วิ) เรียก `touch_job` ระหว่าง graph ทำงาน — ticker อยู่ที่ runner ไม่ใช่ใน node ดังนั้น **หัวใจเต้น = process ยังไม่ตาย แม้กำลังรอ LLM call นานๆ** / หัวใจหยุด = event loop ตายจริง
- [jobs API](../../../backend/app/api/routes/jobs.py): response เพิ่ม `heartbeat_at`, `heartbeat_age_s`, `health: working|stalled` (stalled = age ≥ 30 วิ)
- [frontend/app.py](../../../frontend/app.py) `_render_progress`: 3 สถานะแยกชัดด้วยสายตา — ✅ ทีมยังทำงานอยู่ (heartbeat X วิที่แล้ว) / ⚠️ ติดต่อ backend ไม่ได้ (httpx error ตอน poll) / ❌ job failed — พร้อม elapsed ต่อ step
- Sub-step notes: service เล็ก `progress_reporter.py` → `note_substep(thread_id, text)` ให้ [data_analyst.py](../../../backend/app/agents/data_analyst.py) รายงาน "SQL รอบที่ 2/3" ระหว่าง retry loop

### G1b — Feedback capture (ดึงมาจาก Phase J โดยเจตนา — labels ใช้เวลาสะสมเป็นเดือน)
- ตารางใหม่ใน chat SQLite ([chat_store.py](../../../backend/app/services/chat_store.py)):
  ```sql
  CREATE TABLE IF NOT EXISTS answer_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL, message_id INTEGER, job_id TEXT,
    rating TEXT NOT NULL,            -- 'up' | 'down'
    reason_tag TEXT,                 -- 'wrong_number'|'wrong_metric'|'too_slow'|'unclear'|NULL
    comment TEXT, corrected_answer TEXT, created_at TEXT NOT NULL
  );
  ```
- Route ใหม่ `api/routes/ratings.py` (`POST /api/v1/chat/rating`, `GET /api/v1/chat/ratings`) + ปุ่ม 👍/👎 + reason + ช่องแก้คำตอบ ใต้ทุกคำตอบสุดท้ายใน frontend

### G2 — Executable Metric Registry (หัวใจของทั้ง roadmap)
ที่บ้านหลังเดียวของนิยาม KPI ทุกตัว — versioned, dialect-aware, HITL-gated — ตอบโจทย์ "มืออาชีพต้องรู้คำถามพื้นฐานของ role ตัวเอง" ด้วยการทำให้คำถามเหล่านั้น **เป็นสูตรที่ execute ได้จริง** ไม่ใช่แค่ prompt text

- ไฟล์ใหม่: `backend/app/services/metric_registry.py` → store ที่ `data/local/knowledge/metric_registry.json` ตาม pattern ของ [knowledge_store.py](../../../backend/app/services/knowledge_store.py) (asyncio lock, atomic tmp-file write, lifecycle `draft → approved → deprecated`, เข้า prompt เฉพาะ approved)
- Entry schema:
  ```json
  {
    "metric_key": "metric.gross_profit",
    "name_th": "กำไรขั้นต้น", "name_en": "Gross Profit",
    "version": 1, "status": "approved", "theme": "sales",
    "table": "SAPHANADB.CE1SATG_All_Cleaned",
    "time_column": "SourceMonth", "time_format": "YYYYMM",
    "expression": "(CAST(Inter_Company AS DECIMAL(18,2)) + CAST(Revenue AS DECIMAL(18,2)) + CAST(Return_Revenue AS DECIMAL(18,2))) - CAST(COGS_Actual AS DECIMAL(18,2))",
    "aggregation": "SUM",
    "dimensions": ["Customer", "Product_Number", "Profit_Center", "Sales_Organization", "Material_Group_MATKL"],
    "unit": "THB",
    "derived": null,
    "baseline_question_tags": ["gross_profit", "qoq", "yoy"],
    "source": "owner_seed", "owner_confirmed": true,
    "history": [{"version": 1, "changed_at": "...", "reason": "seed"}]
  }
  ```
  metric อนุพันธ์ (GP%, QoQ, YoY, sales/customer, discount rate) ใช้ `"derived": {"kind": "ratio"|"period_delta", "of": "...", "over": "...", "lag_months": 3}` — คำนวณใน Python จาก snapshot ไม่ใช่ใน SQL
- **Renderer กลางตัวเดียว** `render_metric_sql(entry, source, *, months=None, dimension=None)` — จัดการ dialect quoting (`[..]` vs `".."`), CAST ทุก measure (ทุกคอลัมน์ CE1SATG เป็น varchar — บทเรียน Phase F ถูก institutionalize ที่นี่), และความรู้จาก [pg_numeric_overlay.py](../../../backend/app/services/pg_numeric_overlay.py) — จุดนี้คือสิ่งที่ทำให้ scheduled pipeline ไม่ต้องพึ่งวินัยของ LLM
- Seed ~12 metrics จากคำถามพื้นฐานของ role: `revenue`, `revenue_plus_inter`, `gross_profit`, `gp_pct`, `net_profit` (draft — รอ O-1), `sales_quantity`, `sales_per_customer`, `product_champion` (top-N by revenue), `discount_rate` (draft — รอ O-2), `qoq_revenue`, `yoy_revenue` (รอ O-3), `customer_new`, `customer_churn` — สูตร "Fabric cleaned:" ที่มีอยู่ใน glossary migrate เข้า registry (glossary ยังเป็น fallback)
- Integration: DA prompt ได้ block `{metric_registry_context}` (approved เท่านั้น), [insight_starter_service.py](../../../backend/app/services/insight_starter_service.py) เปลี่ยนมาอ่าน registry, [promotion_service.py](../../../backend/app/services/promotion_service.py) ใช้ approve draft→approved, route ใหม่ `api/routes/metrics.py` (CRUD + `POST /metrics/{key}/preview` รันจริง ≤12 แถวผ่าน guard เดิม), seed script `scripts/seed_metric_registry.py` + `.ps1`

### G3 — Golden-question eval v1: ไม้บรรทัดวัดความเก่ง
- ไฟล์ใหม่: `backend/app/services/eval_service.py`, `scripts/run_golden_eval.py` + `.ps1`, คำถามที่ `data/local/eval/golden_questions.json`, ผลที่ `data/local/eval/results/{run_id}.json`
- Question schema:
  ```json
  {"id": "gq-001", "question_th": "ยอดขายรวมไตรมาสล่าสุดเท่าไร", "theme_id": "sales",
   "expected_metric_key": "metric.revenue_plus_inter",
   "reference": {"kind": "metric_registry", "months": "latest_quarter"},
   "tolerance_pct": 1.0, "expected_keywords_th": ["ไตรมาส"],
   "source": "baseline_seed", "active": true}
  ```
- Grading **deterministic**: รันคำถามผ่าน chat pipeline ปกติ → ดึงตัวเลข/SQL จากคำตอบ → เทียบกับค่าอ้างอิงที่ render จาก registry บน source เดียวกัน ± tolerance + เช็ค keyword/latency → aggregate เป็น `accuracy_pct`, `sql_success_rate`, `median_latency_s`
- Seed ~20 ข้อ (2 ข้อต่อ baseline tag) — **รัน baseline ครั้งแรกและบันทึกผลก่อนเริ่ม Phase H ใดๆ ทั้งสิ้น**
- แหล่งคำถามเพิ่มอัตโนมัติในอนาคต: ทุก 👎 ที่มี corrected_answer และทุก insight ที่ถูกกดว่า "ข้อมูลผิด" กลายเป็น golden-question candidate

### เกณฑ์สำเร็จ Phase G
- Heartbeat มองเห็นภายใน 30 วิในทุกสถานการณ์ — ไม่มีสถานะ "ไม่รู้ว่าเป็นอะไร" อีกต่อไป
- Registry ≥ 12 metrics โดย owner approve ≥ 8
- Baseline eval run ถูกบันทึก (เลขเท่าไหร่ก็ได้ — มันคือจุดตั้งต้น)
- answer_ratings เริ่มสะสม (นับจำนวนโตขึ้น)

---

## 7. Phase H — Analytics Engine: สมองสถิติจริง (Effort L, ~3–4 สัปดาห์ | ต้องมี G2)

> เป้าหมาย: ระบบ "อ่านข้อมูลเองเป็น" ด้วยคณิตศาสตร์จริง — นี่คือจุดที่ machine learning เข้าบ้านครั้งแรก

- **Task 0**: verify cp314 Windows wheels ของ pandas/numpy/scipy (+statsmodels) → pin version ใน `backend/requirements.txt`
- **`backend/app/analytics/` — pure functions, zero I/O, zero LLM** (unit-test offline ได้ 100% ด้วย synthetic series ใน `backend/tests/test_detectors.py`):
  - `detectors.py` — anomaly: robust z-score (median/MAD), IQR fence, STL-residual (ถ้า statsmodels import ได้); changepoint: CUSUM (numpy ล้วน ไม่เพิ่ม dependency); trend: Theil-Sen slope + Mann-Kendall significance (scipy)
  - `forecasting.py` — baseline: seasonal naive (m=12) เสมอ; ETS เมื่อ statsmodels มี; detector = actual หลุด forecast interval
  - `contribution.py` — **ท่าเซ็นของ GA Insights**: แยก Δ ของ metric ระหว่าง 2 periods ตาม dimension → top-k drivers พร้อม share-of-change + mix-vs-rate split สำหรับ ratio metrics ("GP% ตกเพราะ volume ลูกค้า A หรือเพราะ margin สินค้า B?")
  - Pareto/champion + concentration (HHI), churn (เคยมี revenue ≥2 ใน 6 เดือนก่อน แต่เป็นศูนย์ 2 เดือนล่าสุด) / new-customer detection
- **Snapshot store** — `backend/app/services/snapshot_store.py` → `data/local/analytics/analytics.db` (WAL):
  ```sql
  metric_snapshots(metric_key TEXT, period TEXT, dim_name TEXT, dim_value TEXT,
                   value REAL, row_count INTEGER, source TEXT, refreshed_at TEXT,
                   PRIMARY KEY(metric_key, period, dim_name, dim_value));
  snapshot_runs(id TEXT PRIMARY KEY, started_at, finished_at, source, status,
                metrics_refreshed INTEGER, months_window TEXT, error TEXT);
  ```
  (`dim_name='__total__'` = อนุกรมรวม; ประมาณการ volume: 6 metrics × 36 เดือน × ~1.7k dim values ≈ ไม่ถึง 500k แถว — จิ๊บจ๊อยสำหรับ SQLite)
- **`snapshot_refresh_service.py`** — render SQL จาก registry ต่อ metric × dimension (`GROUP BY SourceMonth, dim`) → รันผ่าน `run_sql` + `get_active_sql_source()` + guard เดิมทุกตัว → upsert; รอบแรก backfill 36 เดือน, รอบถัดไป refresh 3 เดือนท้าย (รองรับ SAP restatement); provenance บันทึกทุก run
- Route ใหม่ `api/routes/analytics.py`: สถานะ snapshot, อ่าน series, ปุ่ม refresh (job kind `snapshot_refresh` ผ่าน job_runner)
- Integration: DS agent prompt ได้ `{analytics_context}` = สรุปผล detector ล่าสุดของ theme — **DS เริ่มพูดด้วยสถิติที่คำนวณจริง ไม่ใช่สมมติฐานลอยๆ**

### เกณฑ์สำเร็จ Phase H
- Backfill 36 เดือนเสร็จ < 10 นาทีบน mirror; incremental run < 2 นาที
- Detector test suite green แบบ offline ทั้งชุด
- Detectors จับ event ในอดีตที่ owner รู้อยู่แล้วได้ ≥ 3 กรณี (เช่น เดือนที่ยอดขายตกจริง) — validation ด้วย script เทียบกับความจริงที่คนรู้

---

## 8. Phase I — Proactive Insight Pipeline: ทำงานเองไม่ต้องรอถาม (Effort L, ~3–4 สัปดาห์ | ต้องมี H + G1b)

> เป้าหมาย: ตื่นเช้ามาเปิดหน้า Insights แล้วเจอ "เมื่อคืนระบบพบอะไร" — GA Insights ของข้อมูลตัวเอง

- **Store** — `insight_store.py` (ใน analytics.db):
  ```sql
  insights(id TEXT PRIMARY KEY, run_id TEXT, created_at TEXT, theme_id TEXT,
           metric_key TEXT, detector TEXT, dim_name TEXT, dim_value TEXT,
           period TEXT, direction TEXT, magnitude REAL,
           significance REAL, impact REAL, novelty REAL, score REAL, rank_score REAL,
           status TEXT, evidence TEXT,      -- JSON: series window, stats, drivers, rendered SQL, agg rows
           narrative_th TEXT, narrated_at TEXT, published_at TEXT,
           source TEXT, expires_at TEXT);
  insight_feedback(id TEXT PRIMARY KEY, insight_id TEXT,
                   label TEXT,              -- 'useful' | 'not_useful' | 'wrong'
                   comment TEXT, user_id TEXT, created_at TEXT);
  ```
- **Pipeline** — `insight_pipeline.py` เป็น job kind ใหม่ผ่าน job_runner (steps โชว์ใน progress timeline เดิม): `refresh_snapshots → run_detectors → score_candidates → narrate_top → publish`
- **Scheduler** — `scheduler_service.py` (APScheduler ใน lifespan ของ [main.py](../../../backend/app/main.py)) + config ใหม่ใน [config.py](../../../backend/app/core/config.py): `insight_pipeline_enabled`, `insight_cron_hour=2`, `insight_narrate_top_k=8`, `insight_catchup_after_hours=24` — catch-up-on-startup เป็นหลัก (ดู locked decisions), sidebar แสดง "insight รอบล่าสุด: X ชม. ที่แล้ว"
- **Scoring**: `score = significance_norm × impact_norm × novelty` — impact = |Δ| เทียบกับยอดรวมรายเดือนของ metric, novelty = dedupe กับ insight (metric, dim, direction) เดิมภายใน 60 วัน (กดซ้ำให้เงียบ, เรื่องใหม่ให้เด่น)
- **Narration (Ollama, ไทย)**: prompt แบบ evidence-only — input คือ evidence JSON, output 3–5 ประโยค + คำถามต่อยอด 1 ข้อ; **numeric validator บังคับ** (หลักการใหญ่ข้อ 1); narrate เฉพาะ top-K (8) แบบ eager ที่เหลือ lazy ตอน card ถูกเปิดดูครั้งแรก (ประหยัด CPU)
- **UI** — เปลี่ยนเป็น Streamlit multipage: `frontend/pages/insights.py` — GA-style cards: หัวข้อไทย, metric + period, direction badge, impact (บาท), sparkline, narrative, evidence เปิดดูได้ (SQL + แถว aggregate + สถิติ detector), ปุ่ม feedback 3 ปุ่ม (**มีประโยชน์ / ไม่มีประโยชน์ / ข้อมูลผิด**) + comment; อ่าน feed ผ่าน `st.cache_data(ttl=30)` — ไม่เพิ่ม fragment poll ใหม่

### วงจรชีวิตของ insight (lifecycle)
```
detector emit
   │
   ▼
candidate ──► scored ──┬──► suppressed   (novelty dedupe / ต่ำกว่า publish bar)
                       ├──► expired      (period เก่าเกิน)
                       └──► narrated (top-K, ตัวเลขผ่าน validator)
                                │
                                ▼
                            published (ติด provenance 🟦 fabric / 🟨 postgres)
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
           useful           not_useful           wrong
         (label=1)          (label=0)          (label=0 + auto-สร้าง
              │                 │               golden-question candidate
              └────────┬────────┘               + draft ให้ owner ตรวจ
                       ▼                          สูตร/data quality)
             ranker training data (Phase J)
                       │
                       ▼
             archived (หมดอายุ 45 วัน, config ได้)
```

### เกณฑ์สำเร็จ Phase I
- Pipeline รันจบเอง unattended (nightly หรือ catch-up) ต่อเนื่อง
- ≥ 5 insights เผยแพร่/สัปดาห์; ≥ 30% ถูกกด "มีประโยชน์" ภายในเดือนแรก (เกณฑ์สมจริงระดับ GA Insights); "ข้อมูลผิด" < 10%
- Detection latency ≤ 24 ชม. หลังข้อมูลลง mirror
- ตัวเลขใน narrative ที่ไม่อยู่ใน evidence = **0 กรณี**

---

## 9. Phase J — Learning Loops: เก่งขึ้นแบบพิสูจน์ได้ (Effort L, ~4 สัปดาห์ | ต้องมี labels สะสมจาก G + feed จาก I)

> เป้าหมาย: ปิดวงจร "ทำ → ผิด/ถูก → จำ → ทำดีขึ้น" ทั้ง 4 วง — และ ML ตัวแรกที่เรียนรู้จาก user จริงเกิดที่นี่

| วงจร | ไฟล์ใหม่ | กลไก |
|---|---|---|
| จำความสำเร็จ | `sql_pattern_store.py` | เก็บ (คำถาม, SQL ที่รันสำเร็จ, dialect, tables, embedding) หลัง DA execute สำเร็จ + quality ยืนยัน → retrieval top-3 คำถามคล้าย (dialect-matched, ไม่เคยโดน 👎) เป็น few-shot ใน DA prompt |
| เรียนจากความผิด | `lesson_miner.py` | ขุด [pdca_failures.jsonl](../../../backend/app/services/pdca_logger.py) ที่วันนี้ write-only → cluster ตาม error class (reuse `_classify_sql_error`) → `data/local/knowledge/sql_lessons.json` top-10 บทเรียนสั้นๆ → เข้า DA prompt; รันรายสัปดาห์ผ่าน scheduler |
| เรียนจาก feedback | `insight_ranker.py` | features: detector, metric, dim, impact, significance, recency; labels จาก insight_feedback — heuristic จน ≥ 100 labels → **logistic regression** (เพิ่ม scikit-learn ตอนนี้) → `data/local/models/insight_ranker.pkl`, retrain รายสัปดาห์, **AUC gate ≥ 0.6** ไม่ผ่านใช้ heuristic ต่อแบบ log ไว้ — นี่คือโมเดล ML ตัวแรกที่เรียนรู้รสนิยม/ความสำคัญทางธุรกิจจาก owner โดยตรง |
| ความจำแบบ semantic | `embedding_service.py` | Ollama `nomic-embed-text` + numpy cosine → upgrade retrieval ใน [context_nodes.py](../../../backend/app/agents/context_nodes.py) / team memory / feedback context จาก char-budget truncation → top-k ตามความเกี่ยวข้องกับคำถามปัจจุบัน |

### เกณฑ์สำเร็จ Phase J (วัดกับ baseline จาก G3 ทั้งหมด)
- Golden-question accuracy **+≥ 10 จุด** จาก baseline
- SQL retry ต่อคำถามลดลง ≥ 30% (วัดจาก PDCA log)
- Ranker AUC ≥ 0.65 เมื่อ trained; สัดส่วน "มีประโยชน์" ใน top-5 ของ feed ดีขึ้น month-over-month

---

## 10. Phase K — World-class Layer: ทีมมืออาชีพที่พัฒนาตัวเอง (Effort M–L, ongoing | ต้องมี I + J)

- **Board digest อัตโนมัติราย สัปดาห์/เดือน** — `digest_service.py` (reuse pattern จาก [briefing_service.py](../../../backend/app/services/briefing_service.py)): รวม insights ที่ published+useful + ตาราง QoQ/YoY + metric summary → `data/local/briefings/digests/{yyyy-ww}.json` → `frontend/pages/digest.py`; optional ส่งให้ Claude consultant ขัดเกลา (redaction/audit เดิมของ Phase 3 บังคับใช้)
- **Role curriculum self-development (absorb Phase C เดิม)** — `data/local/knowledge/curriculum/{role}.json`: question bank ของแต่ละ role seed จากคำถามพื้นฐานที่มืออาชีพต้องถามเอง (DA: ยอดขาย/GP/NP รายไตรมาส, ยอดขายต่อลูกค้า, product champion, discount rate, QoQ/YoY, ความผิดปกติของยอดขาย, ลูกค้าเพิ่ม/หาย; DS: seasonality, driver analysis; DE: data quality, freshness; BA: เป้า vs จริง, story ผู้บริหาร) → nightly `study` job (kind ใหม่ตามที่จองไว้ใน phase-3-consultant) หยิบ 1–2 ข้อรันผ่าน graph ปกติช่วงเครื่องว่าง → ผลเข้า team memory สถานะ**รอ CEO approve** (HITL เดิม) → ทุกข้อที่ทำเสร็จรัน golden question ที่ match กัน — **progress ของ curriculum เป็นตัวเลข ไม่ใช่คำโฆษณา**
- **Cross-theme knowledge aggregation** — service รวม glossary/relationships/lessons ที่ approved ข้าม theme เป็น global layer + per-theme override
- **(Optional, absorb Phase E เดิม)** — sandboxed Python execution สำหรับ DS agent + model persistence; ตาม locked decision ของ phase-d: Docker ใช้ได้เฉพาะ `execute_python` เท่านั้น; เขียน doc แยกเมื่อจะทำจริง

### เกณฑ์สำเร็จ Phase K
- Digest ออกอัตโนมัติต่อเนื่อง ≥ 4 สัปดาห์
- ทุก role มี curriculum pass-rate เป็นตัวเลขที่โตขึ้น
- Owner ยืนยัน "ระบบฉลาดขึ้นจริง" โดยมี **eval trend chart** (จาก G3 ถึงปัจจุบัน) เป็นหลักฐานรองรับ ไม่ใช่ความรู้สึก

---

## 11. Sequencing + Effort

| Phase | Effort | ต้องมีก่อน | ทำคู่ขนานกับ |
|---|---|---|---|
| G1/G1b heartbeat + ratings | S | — | ทุกอย่าง |
| G2 metric registry | M | owner ตอบ O-1..O-3 (สำหรับ metric ที่เป็น draft) | G1 |
| G3 eval baseline | S–M | G2 (ค่าอ้างอิง) | เตรียม H |
| H analytics engine | L | G2; cp314 wheels; การปิด D-1/D-2 (Phase F) ช่วยให้เชื่อเลขฝั่ง Postgres ได้เต็มที่ | G3 |
| I proactive pipeline | L | H, G1b | ชิ้น capture ของ J |
| J learning loops | L | labels สะสมตั้งแต่ G; feed จาก I | ออกแบบ digest ของ K |
| K world-class | M–L | I, J | — |

**2 สัปดาห์แรกของ Phase G (slice แรกที่จับต้องได้):**
- สัปดาห์ 1: heartbeat column + ticker + `health` field + frontend 3 สถานะ; ตาราง `answer_ratings` + endpoint + ปุ่ม 👍/👎; tests (`test_job_heartbeat.py`, `test_ratings_api.py`)
- สัปดาห์ 2: `metric_registry.py` + seed 12 metrics (draft, owner approve ≥ 8) + registry context เข้า DA prompt (หลัง config flag); `eval_service.py` skeleton + golden questions 10 ข้อ + **บันทึก baseline run ครั้งแรก** — เลขที่ทุกอย่างหลังจากนี้ถูกวัดเทียบ

---

## 12. ความเสี่ยงและการรับมือ

| # | ความเสี่ยง | การรับมือ |
|---|---|---|
| 1 | Python 3.14 wheels บน Windows (statsmodels/sklearn อาจตามหลัง) | verify ก่อน commit (task 0 ของ H); detectors ออกแบบให้ numpy/pandas/scipy พอ, statsmodels เป็น optional import-guarded; pin versions |
| 2 | Ollama CPU ช้าตอน narrate | eager แค่ top-K (8), ที่เหลือ lazy; รันตี 2 / catch-up defer เมื่อมี chat job; `keep_alive` + `num_predict` bound เดิมช่วยอยู่แล้ว |
| 3 | Backend ไม่ได้รันตลอด → nightly cron ไม่ยิง | **catch-up-on-startup เป็นกลไกหลัก** (เช็ค staleness กับ `snapshot_runs`), cron เป็นโบนัส; sidebar โชว์ความสดของรอบล่าสุด; ปุ่ม manual run |
| 4 | Load บน mirror จาก snapshot refresh | aggregate GROUP BY บน 1.6M แถวถูกมากสำหรับ Postgres; incremental 3 เดือน; product cap top-500; serialize ผ่าน job runner; row-count guard เดิม |
| 5 | varchar measures (ทุกคอลัมน์ CE1SATG) | CAST อยู่ใน registry template ทุกตัว (บทเรียน Phase F ฝังเป็นสถาบัน); SQL ใน scheduled path render แบบ deterministic ไม่พึ่ง LLM |
| 6 | SQLite contention กับ UI ที่ poll ทุก 3 วิ | แยกไฟล์ `analytics.db` + WAL; app.db ไม่ถูกแตะโดย pipeline; writer อยู่ใน backend process เดียว |
| 7 | Streamlit polling บวม | insight feed ใช้ `st.cache_data(ttl=30)`; fragment 3 วิมีแค่ตัวเดิมของ chat job |
| 8 | Hallucination ใน insight | evidence-first invariant + numeric validator ทุก narrative + provenance label ทุก insight (สอดคล้อง Phase F) |
| 9 | Labels น้อยเกินกว่า ranker จะเรียน | เริ่ม capture ตั้งแต่ G (ไม่ใช่ J); heuristic จนกว่า ≥ 100 labels + AUC gate ชัดเจนก่อนสลับ |
| 10 | ความกำกวม fiscal calendar (QoQ/YoY) | open item O-3 ต้องตอบก่อน seed metric แบบ period_delta — ล็อกไว้ในเอกสารนี้แล้ว |

---

## 13. Verification (ของ roadmap นี้เอง และของแต่ละ phase เมื่อทำจริง)

**เอกสารนี้:**
1. Owner อ่านทบทวน open items O-1..O-3 (§5) และตอบก่อนเริ่ม G2
2. เมื่อเริ่มแต่ละ phase → สร้าง phase doc จาก [_TEMPLATE-phase.md](_TEMPLATE-phase.md) และปฏิบัติตาม §4 Delegation Guardrails (Handoff Protocol §4.4) โดยอ้างกลับมาที่ roadmap นี้
3. ผู้ตรวจใช้ Reviewer Checklist (§4.5) — conformance tests + phase doc + gates/ คือหลักฐานที่ไม่ต้องเชื่อคำรายงาน

**หลักการ verify ประจำทุก phase (สรุปจากเกณฑ์สำเร็จรายบท):**
- Phase G: heartbeat เห็นใน 30 วิทุกกรณี / registry ≥ 12 (approved ≥ 8) / **baseline eval ถูกบันทึก** / ratings สะสม
- Phase H: backfill < 10 นาที / detector suite green offline / จับ event อดีตที่ owner รู้ ≥ 3 กรณี
- Phase I: รัน unattended / ≥ 5 insights/สัปดาห์, useful ≥ 30%, wrong < 10% / เลขหลุด evidence = 0
- Phase J: accuracy +≥ 10 จุด / retry −30% / AUC ≥ 0.65
- Phase K: digest ≥ 4 สัปดาห์ต่อเนื่อง / curriculum pass-rate โตขึ้น / eval trend chart ยืนยัน "ฉลาดขึ้นจริง"
