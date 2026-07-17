# Phase D — อุด Pipeline เดิม (Data Filtering, Row-Size Guard, Retry Loop, PDCA Logging)

> **สถานะ:** วางแผนแล้ว (2026-07-17) — รอทีมงาน implement ตามเอกสารนี้ แล้วให้ตรวจสอบความเรียบร้อยอีกครั้งก่อนไปต่อ
> **ผู้ดำเนินการ:** ทำตามลำดับ D1 → D6 (D2/D3 ผูกกันเป็น retry loop เดียว ควรทำคู่กัน), เขียน test ควบคู่ไปกับแต่ละข้อ ไม่ใช่ทำทีหลังทั้งหมด
> **หลักการใหญ่:** เอกสารนี้คือ "เสาหลักที่ 1 (Data Pipeline & Memory) + เสาหลักที่ 2 (Agent Orchestration & PDCA Error Loop)" จาก 4 เสาหลักที่ owner ต้องการ integrate เข้าระบบ AI Data Team เดิม — เสาหลักที่ 3 (Sandboxed Execution) และ 4 (Model Persistence) อยู่นอกขอบเขตเอกสารนี้ ดู "Phase E" ท้ายเอกสารสำหรับ roadmap ระดับสถาปัตยกรรม (ยังไม่ลงรายละเอียด implementation — ออกแบบละเอียดหลัง Phase D ใช้งานจริงแล้ว เพราะ Phase E พึ่งพา infra ที่ Phase D สร้างโดยตรง)

---

## การตัดสินใจที่ล็อกแล้ว (ห้ามเปลี่ยนโดยไม่ถาม owner)

| หัวข้อ | ตัดสินใจ |
|---|---|
| Sandbox (Phase E, อ้างอิงล่วงหน้า) | ใช้ Docker **เฉพาะตัว execute_python** เท่านั้น — backend/frontend ยังรัน native ตามเดิมทั้งหมด ไม่ขัดกับหลักการ "Windows-native, no Docker" ของ path หลัก |
| ขอบเขต Phase D vs E | แบ่ง 2 phase ชัดเจน — Phase D (เสาหลัก 1+2, อุดช่องโหว่ pipeline **เดิม**, เสี่ยงต่ำ) ทำก่อน แล้วค่อย Phase E (เสาหลัก 3+4, ความสามารถ**ใหม่**ทั้งหมด, ใหญ่กว่ามาก) |
| Row-size safety net | ใช้ **pre-flight `COUNT(*)`** ก่อนรันคำสั่งจริงเสมอ (ไม่ใช่แค่ post-fetch cap แบบเดิม) — ยอมรับ round-trip เพิ่ม 1 ครั้งต่อ query เพื่อความแม่นยำ (ตรงกับหลัก "accuracy over speed" ของโปรเจกต์) |
| Retry cap | สูงสุด **3 ครั้ง** ต่อคำถามหนึ่งข้อ ก่อน graceful-degrade ให้ CEO |
| Timeout | Job ทั้งงาน (chat job) ต้องไม่ค้างเกิน `chat_job_max_seconds` (ตั้งต้น 1200s ให้สอดคล้องกับ Phase E ที่จะใช้ 20 นาทีเป็น cap ของ Python execution) |

---

## ผล Deep Audit ก่อนวางแผน (อ่านโค้ดจริง ณ วันที่วางแผน — ใช้ยืนยัน baseline ก่อนแก้)

| หัวข้อ | สถานะปัจจุบัน (ก่อน Phase D) |
|---|---|
| SQL filtering | `sql_guard.py` บล็อคแค่ DDL/DML + multi-statement (INSERT/UPDATE/DELETE/DROP/EXEC/xp_/sp_ ฯลฯ) — **ไม่บล็อค `SELECT *`, ไม่บังคับ WHERE**, ไม่มี cost/scan analysis ใดๆ |
| Row cap | `fabric_max_rows=100` (config.py) บังคับผ่าน **post-fetch `cursor.fetchmany(100)`** เท่านั้น (`fabric_connector.py:execute_read_only`) — ไม่มี `TOP`/`LIMIT` ฝังในตัว SQL, Fabric server คำนวณ full result set เสร็จก่อนแล้วค่อยตัดฝั่ง client — ไม่มี pre-execution size check |
| Retry loop | ไม่มีที่ระดับ LangGraph เลย — `AgentState` ไม่มี retry counter, ไม่มี loop-back edge ใน `orchestrator.py`. มีแค่ retry เดี่ยว 1 ครั้งใน `data_analyst.py::_retry_sql_with_error` เฉพาะ error `"Invalid column name"`/`42S22` เท่านั้น |
| Graceful degradation | ไม่มีจริง — raw error string (เช่น `f"SQL_ERROR: {e}"`) ไหลตรงเข้า `final_answer` ที่ CEO เห็น, `quality_gaps`/`step_errors` ไม่เคยถูก render เป็นข้อความใน BA narrative |
| Timeout | มีแค่ per-call timeout (Ollama 600s ผ่าน httpx client_kwargs, Fabric query 300s ผ่าน pyodbc `conn.timeout`) — **ไม่มี wall-clock cap ระดับทั้ง job** (`asyncio.wait_for` ไม่มีที่ไหนในระบบเลย) |
| Failure logging | มีแค่ `data/local/logs/backend.log` (ephemeral) + note ที่ถูกตัดเหลือ 500 ตัวอักษรใน `job_store` — ไม่มี persistent log ที่เก็บ (user prompt + SQL + traceback) ครบ |
| File storage | ผล query อยู่ใน memory ล้วน (`list[dict]`) ไม่เคยเขียนลงดิสก์เลย — ไม่มี `local_data/`, ไม่มี cleanup cron ใดๆ ทั้งระบบ (แม้แต่ `discovery.json` sample_rows ก็ไม่มี TTL/cleanup) |
| Credential/read-only | **ดีอยู่แล้ว ไม่ต้องแก้**: `fabric_client_secret`/`anthropic_api_key` ไม่เคยหลุดเข้า prompt agent ไหนเลย (confirmed by grep), read-only ถูก code-enforce จริงผ่าน `sql_guard.py` ไม่ได้พึ่งแค่สิทธิ์ Service Principal |

---

## งานที่ต้องทำ

### D1 — Row-size safety net: pre-flight `COUNT(*)`

ใหม่ใน `backend/app/services/fabric_sql.py` (หรือ `fabric_connector.py` ถ้าเหมาะกว่า):
```python
async def estimate_row_count(sql: str, settings) -> int:
    guard_sql = f"SELECT COUNT(*) AS cnt FROM (\n{sql}\n) AS _guard_cnt"
    # รันผ่าน connector เดิม ใช้ fabric_query_timeout เดียวกับ query จริง
    # ถ้า wrap ไม่ผ่าน (parse error) → fail-open: log warning แล้วปล่อยผ่านไปใช้ post-fetch cap เดิมแทน — ห้ามบล็อกคำถามที่ถูกต้องเพราะกลไก guard เองพัง
```
**⚠️ ข้อควรระวังทาง T-SQL ที่ต้องจัดการ:** SQL Server/Fabric **ไม่อนุญาต `ORDER BY` ใน derived table โดยไม่มี `TOP`/`OFFSET`** — ถ้า SQL ที่ data_analyst สร้างมี `ORDER BY` ท้ายคำสั่ง (มักมีเวลาถาม "TOP N ที่มากสุด/น้อยสุด") การ wrap ด้วย `SELECT COUNT(*) FROM (<query>) AS _guard_cnt` ตรงๆ จะ error ทันที (SQL Server error 1033) ต้อง strip `ORDER BY ...` ท้ายสุดออกก่อน wrap เสมอ (regex หรือ SQL parser ง่ายๆ พอ เพราะ `sql_guard.py` การันตีอยู่แล้วว่าเป็น single SELECT/WITH statement) — เขียน unit test เฉพาะเคสนี้ เพราะเป็นจุดที่มีโอกาสพังเงียบๆ สูงสุด

`config.py` เพิ่ม `fabric_row_count_threshold: int = 50000` (ปรับได้ทีหลังตามการใช้งานจริง) — ถ้า estimate เกิน threshold → คืน error แบบมีโครงสร้าง (ไม่ใช่ raise ทั่วไป) เช่น `RowCountExceeded(estimated=N, threshold=T)` ให้ data_analyst จับได้เหมือน error class อื่นๆ เพื่อไหลเข้า retry loop (D2) — ข้อความบอก agent ให้ปรับ WHERE ให้แคบลง (ระบุช่วงเวลา/หน่วยงาน/เงื่อนไข)

`data_analyst.py` SYSTEM_PROMPT: เสริมข้อความชัดเจนว่าห้าม unscoped `SELECT *` บนตารางใหญ่ ต้องมี WHERE ที่ตรงกับคำถาม CEO (ใช้ row count จาก schema context pack ที่มีอยู่แล้วเป็นสัญญาณให้ LLM) — เป็น first-line defense ทางภาษา ส่วน COUNT(*) guard ด้านบนคือ hard enforcement จริงที่พึ่งพาได้

### D2 — Retry loop ทั่วไป (ไม่ใช่แค่ "Invalid column name" แบบเดิม)

- `backend/app/agents/state.py`: เพิ่ม field `sql_retry_count: int = 0`
- `backend/app/agents/orchestrator.py`: เพิ่ม conditional loop-back edge หลัง node `data_analyst` — ถ้า SQL ล้มเหลว (column error / `RowCountExceeded` จาก D1 / SQL error class อื่น) และ `sql_retry_count < 3` → วนกลับไป `data_analyst` (เพิ่ม counter ทุกครั้งที่วน) แทนที่จะไปต่อ `summarize`/`explore_critique` ตรงๆ ตามที่เป็นอยู่ตอนนี้
- `data_analyst.py`: ขยาย `_retry_sql_with_error` เดิมให้ handle ได้หลาย error class (ปัจจุบัน hardcode เฉพาะ `42S22`) — ส่ง error message ที่เหมาะกับแต่ละ class เข้า prompt ให้ LLM แก้ไข (เช่น column ผิด → บอกชื่อ column ที่ถูก, row count เกิน → บอกให้เพิ่ม WHERE)
- ครบ 3 ครั้งแล้วยังไม่ผ่าน → set `state.sql_failed = True` พร้อมสรุป error (ไม่ใช่ raw traceback) แล้วปล่อยผ่านไป `summarize` ตามปกติ (ไม่ throw ทำให้ job พังทั้งงาน)

### D3 — Graceful degradation จริง

`backend/app/agents/business_analyst.py` และ/หรือ `quality_assembly.py::format_explore_response_th`: เมื่อ `state.sql_failed` เป็น True หรือ `step_errors` ไม่ว่าง → render ข้อความไทยสุภาพอธิบายว่าทีมลองปรับ SQL แล้ว 3 ครั้งแต่ยังไม่สำเร็จ พร้อมแนะนำให้ CEO ปรับคำถามให้เจาะจงขึ้น (ระบุช่วงเวลา/หน่วยงาน) — **แทนที่** การปล่อย raw exception string (`f"SQL_ERROR: {e}"` เป็นต้น) เข้า `final_answer` ตรงๆ แบบที่เป็นอยู่ปัจจุบัน

### D4 — Wall-clock timeout ระดับ job

`config.py` เพิ่ม `chat_job_max_seconds: int = 1200` — ใช้ `asyncio.wait_for(...)` ครอบ graph execution ใน `job_runner.py::_run_chat_job` กัน job ค้างเกินกำหนดจากผลรวม retry loop ใหม่ (D2) บวก LLM/Fabric latency สะสม — timeout แล้ว mark job `status="failed"` ด้วยข้อความชัดเจน (ใช้ pattern เดียวกับ `asyncio.CancelledError` handling ที่มีอยู่แล้วใน `_run_chat_job`)

**Cleanup ระหว่างทาง (hygiene, ทำพร้อมกันเพราะแก้ `config.py` อยู่แล้ว):** `compose_http_timeout` เป็น setting ที่ grep แล้วไม่ถูกใช้ที่ไหนเลยในระบบ (dead setting) — ลบทิ้ง

### D5 — PDCA persistent log

ใหม่ `backend/app/services/pdca_logger.py` — reuse pattern เดียวกับ `consultant_service.py`'s `consultant_audit.jsonl` (เขียนผ่าน `asyncio.to_thread` กัน block event loop):
```python
async def log_sql_failure(theme_id: str, user_prompt: str, sql: str, error: str, retry_count: int) -> None
```
เขียนไปที่ `data/local/logs/pdca_failures.jsonl` **ทุกครั้ง**ที่ retry ล้มเหลว (ไม่ใช่แค่ครั้งสุดท้าย) — เรียกจาก D2 retry loop ทุก attempt เพื่อให้ review PDCA ย้อนหลังได้ครบทุกรอบความพยายาม ไม่ใช่แค่ผลลัพธ์สุดท้าย

### D6 — เตรียมทาง Phase E (โครงสร้างไดเรกทอรี + cleanup) — ทำตอนนี้กัน rework ทีหลัง

- `backend/app/services/local_paths.py`: เพิ่ม convention ไดเรกทอรี `data/local/local_data/` (ไว้ให้ Phase E ใช้เก็บ `.parquet`/model ชั่วคราว — Phase D เองยังไม่ต้องเขียนอะไรลงตรงนี้ เพราะยังไม่มี Python execution ที่ต้องใช้ไฟล์จริง)
- ใหม่ `scripts/cleanup-local-data.ps1` + คำแนะนำวิธีตั้ง Windows Task Scheduler ใน README: เคลียร์ `local_data/`, log เก่า, job ที่ terminal แล้วเกิน N วันจาก `job_store` — **ยกเว้นเสมอ**: `data/local/team_memory/`, `data/local/knowledge/`, และ (เผื่อ Phase E ในอนาคต) `data/local/models/approved/` — วาง convention ไว้ตอนนี้เพื่อกัน rework ตอน Phase E implement จริง

---

## Tests (mock ทั้งหมด — ไม่ต้องมี Fabric/Ollama จริง ตาม pattern เดิมของ repo)

| ไฟล์ test | ครอบคลุม |
|---|---|
| `test_row_size_guard.py` | `estimate_row_count` wrap SQL ถูกต้อง (รวมเคส `ORDER BY` ต้องถูก strip ก่อน wrap), threshold reject คืน error object ถูกรูปแบบ, fail-open เมื่อ wrap พัง (query แปลกที่ parse ไม่ผ่าน) ไม่บล็อกคำถามที่ถูกต้อง |
| `test_orchestrator_retry.py` | loop-back edge วนได้สูงสุดพอดี 3 ครั้ง (ไม่เกิน ไม่ขาด), แต่ละ error class (`42S22`, `RowCountExceeded`, generic) เข้า retry ได้, ครบ 3 ครั้งแล้ว `sql_failed=True` + graceful message ไม่มี raw traceback หลุดออกไป |
| `test_pdca_logger.py` | JSONL append ครบทุก attempt (ไม่ใช่แค่ final), schema มี prompt/sql/error/retry_count/timestamp |
| ขยาย chat job API test เดิม (`test_chat_job_api.py` หรือเทียบเท่า) | timeout guard (D4) ทำงานจริงเมื่อจำลอง node ช้าเกิน `chat_job_max_seconds`, graceful-degradation response แสดงถูกต้องเมื่อ retry ครบ 3 ครั้ง |

---

## Verification

1. `pytest backend/tests -q` ผ่านทั้งหมด (ของเดิมต้องไม่พัง + เทสต์ใหม่ผ่านครบ)
2. **Manual — oversized query:** ถามคำถามกว้างๆ ที่จะกวาดตารางใหญ่ทั้งตาราง (ไม่ระบุช่วงเวลา/เงื่อนไข) → เห็น COUNT(*) reject ทำงานจริง → DA ปรับ WHERE เองในรอบถัดไป (ไม่เกิน 3 รอบ) → ถ้ายังไม่ผ่านครบ 3 รอบ ต้องเห็นข้อความไทยสุภาพ ไม่ใช่ raw error → เปิด `data/local/logs/pdca_failures.jsonl` เช็คว่ามี entry ครบทุก attempt
3. **Regression:** คำถามที่เคยพังเพราะ column name ผิด (เคสเดิมที่เคยมี auto-fix) ต้องยัง auto-fix ได้เหมือนเดิมภายใต้ retry counter ใหม่ ไม่ถอยหลัง
4. **Timeout:** จำลอง LLM หรือ Fabric ช้าผิดปกติ (mock delay) → ยืนยัน job ไม่ค้างเกิน `chat_job_max_seconds` และ status ออกมาเป็น `failed` พร้อมข้อความชัดเจน
5. **`ORDER BY` edge case:** ถามคำถามที่ทำให้ DA สร้าง SQL แบบ "TOP N เรียงตาม..." (มี `ORDER BY`) → ยืนยัน COUNT(*) guard ไม่ error/ไม่ fail-open โดยไม่จำเป็น

---

## ความเสี่ยง / ข้อควรระวัง

- **Latency เพิ่ม:** COUNT(*) pre-flight เพิ่ม Fabric round-trip 1 ครั้งต่อทุกคำถาม (แม้ query จะเล็กก็ตาม) — ยอมรับได้ตามหลัก "accuracy over speed" ของโปรเจกต์ แต่ควร log เวลาที่ใช้แยกไว้เผื่อต้อง tune threshold/ตัดสินใจ skip guard สำหรับตารางที่รู้แน่ชัดว่าเล็ก (จาก schema context pack row count) ในอนาคต
- **Ollama load เพิ่ม:** retry loop สูงสุด 3 เท่าของการเรียก data_analyst ต่อคำถามหนึ่งข้อที่มีปัญหา — ถูก bound ไว้แล้วที่ 3 ครั้ง ไม่ควรเพิ่มโดยไม่ทบทวน
- **T-SQL derived-table ORDER BY:** ดู D1 — จุดที่พังเงียบที่สุดถ้าไม่ strip ก่อน wrap ต้องมี test เฉพาะ
- **`chat_job_max_seconds=1200` เป็นค่าประมาณ:** ตั้งต้นให้สอดคล้องกับ Phase E (20 นาที) แต่ Phase D เองไม่มี Python execution ที่กิน time ขนาดนั้น — ควร monitor job จริงหลัง deploy แล้วปรับค่าให้เหมาะสมกว่านี้ถ้าจำเป็น (อาจสั้นกว่านี้ได้มากสำหรับ Phase D เพียงอย่างเดียว)

---

## Roadmap ถัดไป (นอกขอบเขตเอกสารนี้)

### Phase E — Sandbox Execution + Model Persistence (เสาหลัก 3 + 4)
พึ่งพา infra ที่ Phase D สร้างโดยตรง (retry counter pattern, `pdca_logger`, graceful degradation) — ขยายกลไกเดียวกันจาก "SQL error" ไปครอบ "Python code error" ด้วย
- **Sandbox:** container Docker แยกต่างหาก (ไม่แตะ backend/frontend ที่ยังรัน native) — `network=none`, mount เฉพาะ `data/local/local_data/{job_id}/`, resource limit (`--memory`/`--cpus`), timeout 1200 วิ บังคับทั้งฝั่ง caller (`asyncio.wait_for`) และในคอนเทนเนอร์เอง (defense-in-depth)
- **DS agent redesign:** จาก critique-only (ปัจจุบัน) → มี tool `run_python` จริง ใช้ retry loop/PDCA log เดียวกับ Phase D
- **File format:** ผลลัพธ์ query ที่จะป้อนให้ Python เขียนเป็น `.parquet` ลง `local_data/{job_id}/` (ต้องเพิ่ม pandas/pyarrow เข้า `requirements.txt` — ยังไม่มีตอนนี้) ใช้ row-size guard จาก Phase D คุมขนาดตั้งแต่ต้นทาง
- **Model persistence:** `.pkl`/`.joblib` ใน `local_data/{job_id}/models/` (โดน cleanup cron ล้างตามปกติ) → HITL "promote to approved" (ต่อยอด pattern approve เดิมของ Knowledge panel) ย้ายไป `data/local/models/approved/{model_id}/` ที่ cleanup script ยกเว้นไว้แล้วจาก D6
- รายละเอียด exact Docker image, tool-calling contract ของ DS, API การ promote model — ออกแบบเป็นรอบใหม่หลัง Phase D เสร็จและผ่านการใช้งานจริงระยะหนึ่ง

### Phase C (เดิม) — พักไว้ รอออกแบบใหม่
Autonomous Study Mode ที่เคยร่างไว้ (scheduler + idle queue, `kind="study"` reuse job runner, deepen team_memory ของธีมเดิม) ยังไม่ถูกยกเลิก — แค่รอออกแบบใหม่อีกครั้งหลัง Phase D/E เสร็จ เพราะ "การบ้าน" ในอนาคตอาจรวมการให้ DS agent ฝึกโมเดลระหว่างว่าง (ใช้ sandbox จาก Phase E) ไม่ใช่แค่ทวน onboarding เหมือนที่ร่างไว้เดิม
