# Phase F — Postgres WH_Silver Mirror (Auto-Fallback Data Source)

> **สถานะ:** งานฝั่งโค้ดทั้งหมดที่ทำได้โดยไม่ต้องรอทีมข้อมูล **เสร็จแล้ว** (auto-fallback `b6eb496` + รอบ hardening ล่าสุด: CAST guidance, numeric overlay, parity script, provenance labels, `/fabric/sources`, UI fallback state) — ยืนยันด้วย automated tests offline ทั้งชุด (207 tests ผ่าน) — **ยังไม่ถือว่า production-verified** จนกว่า (1) ทีมข้อมูล/DBA ปิด D-1/D-2 (2) รัน `scripts/verify_pg_parity.py` กับ live DB ซ้ำหลังแก้ (3) live E2E ผ่าน LLM จริง (ดู "Verification" ท้ายเอกสาร)
> **ผู้ดำเนินการ:** ทีมข้อมูล/DBA ทำ D-1/D-2 (checklist ด้านล่าง) → รัน parity script ยืนยัน → live E2E
> **หลักการใหญ่:** Fabric capacity ไม่เสถียร — Postgres ที่ mirror ข้อมูลเดียวกัน (`fabric_WH_Silver` บน `172.16.0.70`) ใช้เป็น **auto-fallback** เมื่อ Fabric unreachable/paused เท่านั้น ไม่ใช่ตัวแทนถาวร — Fabric ยังเป็น source หลักเสมอ และผลลัพธ์ทุกชิ้นติดป้ายแหล่งข้อมูล (provenance) เสมอ ไม่มี fallback แบบเงียบ

---

## การตัดสินใจที่ล็อกแล้ว (ห้ามเปลี่ยนโดยไม่ถาม owner)

| หัวข้อ | ตัดสินใจ |
|---|---|
| ลำดับ source | Fabric ก่อนเสมอ (ผ่าน reachability cache เดิมจาก Phase D) — Postgres ใช้เฉพาะตอน Fabric unreachable/paused/disabled |
| SQL dialect | ตัดสินใจ dialect (T-SQL vs PostgreSQL) **ก่อน**สร้าง SQL เสมอ ไม่ใช่แปลทีหลัง — DA agent เช็ค active source ก่อนเขียน SQL ทุกครั้ง (รวมตอน retry ถ้า source เปลี่ยนกลางคัน) |
| Postgres connector | `PostgresReplicaConnector` (`backend/app/services/postgres_replica.py`) คู่ขนานกับ `FabricConnector` เดิม ใช้ `sql_guard.py` เดียวกัน (read-only บังคับเหมือนกันทั้งสอง source) |
| Config แยกจาก legacy | `PG_REPLICA_*` ใน `.env` เป็นคนละตัวกับ `POSTGRES_*` เดิม (legacy, เป็น dead code จาก scaffold แรกเริ่ม ไม่เกี่ยวกับ WH_Silver) — ห้ามสับสน/รวมกัน |
| ขอบเขต | `data_engineer.py` (inspection SQL) ยังเป็น Fabric-only ตั้งใจ ไม่ทำ dialect-aware ให้ (ไม่ใช่ core path ที่มีปัญหา Fabric หนัก) |

---

## ผล Deep Audit (live verification จริง ไม่ใช่ unit test mock)

### ✅ ยืนยันแล้วว่าใช้ได้ — กลไก dispatch/execution
- `get_active_sql_source()` เลือก source ถูกต้อง (Fabric ก่อน, fallback Postgres เมื่อ Fabric ปิด/ไม่ตอบ)
- Row-count guard (`enforce_row_count_threshold_for_source`) + `run_sql` dispatch ทำงานจริงกับ `fabric_WH_Silver` (ทดสอบ query จริงผ่าน connector สำเร็จ)
- Dialect fix (`TOP` → `LIMIT`, `GETDATE()` → `NOW()` ฯลฯ) ถูกต้องตามที่ตั้งใจไว้

### ✅ แก้ไขแล้วระหว่างทาง — schema discovery bug
`fetch_schema_summary()` เดิมไม่กรอง Postgres system catalog schema (`pg_catalog`, `information_schema`) ออก ทำให้นับตารางผิด (226 แทนที่จะเป็น 17 ตารางจริง) — Postgres list ตารางระบบตัวเองใน `information_schema.tables` ต่างจาก SQL Server — **แก้แล้ว** เพิ่ม `WHERE table_schema NOT IN ('pg_catalog', 'information_schema')` มี regression test คุมแล้ว (`test_fetch_schema_summary_excludes_postgres_system_catalogs`)

### ✅ แก้ความเข้าใจผิดของตัวเอง — ชื่อคอลัมน์ตรงกัน 100%
รอบแรกเข้าใจผิดว่า Fabric ใช้รหัส SAP ดิบ (`NETWR` ฯลฯ) ต่างจาก Postgres ที่ rename แล้ว — **ผิด**: ตรวจ `discovery.json` จริง (schema cache จาก onboarding) และ live Fabric พบว่า **ทั้งสองฝั่งใช้ชื่อ business-friendly เดียวกัน** (`Billing_Document`, `Net_Value_In_Document_Currency` ฯลฯ) — ยืนยันด้วย screenshot จาก Fabric portal ของ owner ด้วย

**Parity check เต็มรูปแบบ 17 ตาราง (`SAPHANADB` schema, live Fabric vs live Postgres):**

| ผล | ตาราง |
|---|---|
| ✅ ตรงกันสมบูรณ์ (คอลัมน์ + row count) — 16 ตาราง | `ACDOCA_All_Cleaned`, `COSP_All_Cleaned`, `COSS_All_Cleaned`, `CSKT_Cleaned`, `Dim_CSKT_Cleaned`, `Dim_KNA1_Cleaned`, `Dim_MAKT_Cleaned`, `Dim_MARA_Cleaned`, `Dim_SG-A_Dept`, `Dim_SKAT_Cleaned`, `Dim_T001_Cleaned`, `Dim_TVKOT_Cleaned`, `FIELD_DICT_Cleaned`, `SKAT_Cleaned`, `VBRK_All_Cleaned`, `VBRP_All_Cleaned` |
| ⚠️ คอลัมน์ไม่ตรง 1 ตัว — 1 ตาราง | `CE1SATG_All_Cleaned` (ดูรายละเอียดด้านล่าง) |

### ⚠️ ปัญหาจริงที่พบ #1 — column name ถูกตัดทิ้งใน `CE1SATG_All_Cleaned`
- Fabric: `Document_Number_Of_Line_Item_In_Profitability_Analysis_BELNR_SENDER` (**67 ตัวอักษร**)
- Postgres: `Document_Number_Of_Line_Item_In_Profitability_Analysis_BELNR_SE` (**63 ตัวอักษร** — prefix ตรงกันเป๊ะ)

สาเหตุ: PostgreSQL **`NAMEDATALEN` limit** — ชื่อ identifier ยาวเกิน 63 ตัวอักษรจะถูกตัดทิ้งเงียบๆ ตอน `CREATE TABLE` (ไม่ error/warning) ชื่อฟิลด์ SAP นี้ยาว 67 ตัวอักษร โดนตัดอัตโนมัติตอน migrate ไม่ใช่ปัญหาข้อมูล เป็นข้อจำกัดของ Postgres เองที่ migration script ต้องจัดการ (ตั้ง alias/ย่อชื่อเองแทนปล่อยให้ Postgres ตัดแบบเดาไม่ได้)

### ⚠️ ปัญหาจริงที่พบ #2 — data type ไม่ตรงกันในฟิลด์ตัวเลข
ตรวจ `VBRK_All_Cleaned` (158 คอลัมน์): Postgres cast เป็น `numeric(38,10)` เฉพาะ **6 คอลัมน์** ที่เป็นฟิลด์มูลค่า/อัตราแลกเปลี่ยน (`Net_Value_In_Document_Currency`, `Tax_Amount_In_Document_Currency`, `Exchange_Rate_For_Postings_To_Financial_Accounting`, `Credit_Data_Exchange_Rate_At_Billing_Document_Rate`, `Exchange_Rate_For_Letter_Of_Credit_Procg_In_Foreign_Trade`, `UTC_Time_Stamp_In_Long_Form_Yyyymmddhhmmssmmmuuun`) — ส่วนอีก 152 คอลัมน์เป็น `character varying` เหมือน Fabric (Fabric รายงานทุกคอลัมน์เป็น `varchar` ใน `INFORMATION_SCHEMA.COLUMNS` จริง ไม่มีคอลัมน์ไหนเป็น numeric เลยฝั่ง Fabric)

**ทำไมถึงสำคัญ:** T-SQL ยอม implicit convert varchar→numeric กว้างกว่า PostgreSQL ซึ่งไม่ยอมเด็ดขาด (`SUM()`/`AVG()`/comparison บน `character varying` error ทันทีถ้าไม่ cast) — ถ้า DA agent สร้าง SQL แบบไม่ cast อาจผ่านบน Fabric ได้ (implicit convert) แต่จะพังทันทีถ้า fallback ไป Postgres สำหรับ 152 คอลัมน์ที่ยังเป็น varchar (6 คอลัมน์ที่ cast แล้วไม่พังเพราะเป็น numeric จริงอยู่แล้ว) ตรวจแล้วว่า `backend/app/agents/skills/data_analyst/SKILL.md` ไม่มีคำแนะนำเรื่อง CAST เลย — เป็นความเสี่ยงที่มีอยู่แล้วแม้ใช้ Fabric อย่างเดียว แต่ Postgres fallback ทำให้เห็นชัดทันทีเพราะ Postgres strict กว่า

---

## งานที่ต้องการให้ทีมข้อมูล/DBA ตรวจ/แก้ก่อน (D-1, D-2)

### D-1 — แก้ column truncation ใน `CE1SATG_All_Cleaned`
ตั้งชื่อคอลัมน์ `Document_Number_Of_Line_Item_In_Profitability_Analysis_BELNR_SENDER` ให้ตรงกับ Fabric แบบ explicit (alias หรือย่อชื่อเองอย่างตั้งใจ แทนปล่อยให้ Postgres ตัดที่ 63 ตัวอักษรอัตโนมัติ) — เช็คด้วยว่ามีฟิลด์อื่นในอนาคต (ถ้าจะ mirror schema เพิ่ม) ที่ชื่อยาวเกิน 63 ตัวอักษรแบบนี้อีกหรือไม่

### D-2 — ยืนยัน/ส่งมอบ numeric-cast mapping
1. ยืนยันอีก 16 ตาราง (นอกจาก VBRK ที่ตรวจแล้ว) ว่ามี pattern การ cast เดียวกัน (เฉพาะฟิลด์มูลค่า/rate เป็น numeric ที่เหลือเป็น varchar) หรือมีตารางที่ cast มากกว่า/น้อยกว่านี้
2. ตัดสินใจ 1 ใน 2 ทาง:
   - **(ก)** Cast ฝั่ง Fabric ให้ตรงกับ Postgres ด้วย (ถ้าคุมได้) — สะอาดระยะยาวกว่า
   - **(ข) แนะนำ:** ปล่อยให้ต่างกันแบบนี้ต่อไป แต่ส่ง list คอลัมน์ที่เป็น numeric จริงในแต่ละตาราง (ฝั่ง Postgres) ให้ dev ไปทำ CAST guidance ที่ dialect-portable
3. ยืนยัน freshness: Postgres sync ล่าสุดเมื่อไหร่ มี refresh process เป็นระยะหรือไม่ (กัน CEO ได้คำตอบจากข้อมูลเก่าโดยไม่รู้ตัวตอน fallback)

---

## งานฝั่งโค้ด — สถานะล่าสุด

1. ✅ **เสร็จ** — CAST guidance แบบ dialect-portable (`CAST(col AS DECIMAL(18,2))`) เพิ่มแล้วทั้งใน `data_analyst/SKILL.md` (หัวข้อ "Numeric CAST rule") และ `_DIALECT_RULES` ทั้งสอง dialect ใน `backend/app/agents/data_analyst.py` (`_CAST_GUIDANCE`) — มี test คุม (`test_provenance_and_cast.py`) — **ไม่ต้องรอ D-2** เพราะความเสี่ยง implicit-convert มีอยู่แล้วแม้ใช้ Fabric อย่างเดียว
2. ✅ **กลไกเสร็จ, ข้อมูลรอ D-2** — numeric-column overlay: `backend/app/services/pg_numeric_overlay.py` อ่าน `data/local/knowledge/pg_numeric_columns.json` (fallback ไป `data/templates/pg_numeric_columns.template.json` ที่ seed ด้วย 6 คอลัมน์ VBRK ที่ตรวจ live แล้ว) → inject เข้า prompt DA เฉพาะตอน `source="postgres"` (ทั้ง fresh generation และ retry) — ทีมข้อมูลส่ง mapping ครบ 17 ตารางเมื่อไหร่ ให้วางไฟล์ที่ `data/local/knowledge/pg_numeric_columns.json` ได้เลย ไม่ต้องแก้โค้ด — ไฟล์เสีย/หายระบบ degrade เป็น overlay ว่าง ไม่พังเส้นทาง DA
3. ✅ **เสร็จ** — parity script: `scripts/verify_pg_parity.py` (logic เปรียบเทียบอยู่ใน `backend/app/services/schema_parity.py` เพื่อให้ unit-test ได้ offline) — ตรวจ column names + NAMEDATALEN truncation suspects + row counts + type diffs (informational) — read-only ทั้งสองฝั่ง exit code 0/1/2 — รันซ้ำเป็นระยะกัน schema drift
4. ⏳ **ยังบล็อก** — Live E2E ผ่าน LLM จริง (Ollama out-of-memory ฝั่งเครื่อง dev ไม่เกี่ยวกับโค้ด) — ดู checklist ใน "Verification"

### เพิ่มเติมรอบ hardening (production-readiness — สอดคล้อง risk ในเอกสารนี้)

- **Provenance labels** (กัน silent fallback / stale data โดยไม่รู้ตัว): `build_quality_payload` เพิ่ม `data_source` → รายงาน Explore แสดง "แหล่งข้อมูล: Fabric DW / Postgres mirror (สำรอง…) / Offline" — เส้นทาง Trusted (`summarize_node`) ติดป้ายเดียวกัน — backlog item เก็บ `data_source` ถาวร + แสดงใน backlog panel
- **`GET /api/v1/fabric/sources`**: endpoint สถานะ active source + fabric/postgres_replica (configured/reachable/database — ไม่มี secrets) พร้อมข้อความไทย
- **Streamlit sidebar**: เปลี่ยนจาก "Fabric DW" เป็น "แหล่งข้อมูล (Data Source)" — แสดง 3 สถานะชัดเจน: Fabric ปกติ (เขียว) / ใช้ Postgres mirror สำรอง (เหลือง + คำเตือน freshness) / Offline ทั้งคู่

---

## Tests

| ไฟล์ | ครอบคลุม | สถานะ |
|---|---|---|
| `test_postgres_replica.py` | connector: is_configured, connect (readonly+statement_timeout), execute_read_only, fetch_schema_summary (LIMIT ไม่ใช่ TOP, กรอง system catalog) | ✅ ผ่าน |
| `test_sql_source_dispatch.py` | `get_active_sql_source`, reachability TTL cache, `run_sql` dispatch, row-count guard source-aware | ✅ ผ่าน |
| `test_data_analyst_postgres_fallback.py` | DA เขียน SQL ตรง dialect ตาม source, retry สลับ dialect กลางคัน, `_classify_sql_error` รู้จัก psycopg2/Postgres SQLSTATE | ✅ ผ่าน |
| `test_provenance_and_cast.py` | CAST guidance อยู่ใน SKILL.md + ทั้งสอง dialect rules, provenance labels (payload/report/backlog/summarize) ครบ fabric/postgres/offline, backward-compat กับ backlog เก่าที่ไม่มี `data_source` | ✅ ผ่าน (ใหม่) |
| `test_pg_numeric_overlay.py` | overlay: local file > template fallback (VBRK seed), degrade เมื่อไฟล์เสีย/หาย, inject เข้า DA prompt เฉพาะ postgres (fresh + retry), ไม่ inject ตอน fabric | ✅ ผ่าน (ใหม่) |
| `test_schema_parity.py` | comparison logic: NAMEDATALEN truncation detection (case จริงจาก CE1SATG), type diff แบบ informational (case จริงจาก VBRK), drift/missing tables, row-count mismatch, script ปฏิเสธรันเมื่อไม่มี credentials (exit 2) | ✅ ผ่าน (ใหม่) |
| `test_sources_api.py` | `/api/v1/fabric/sources`: active source ทั้ง 3 สถานะ + ไม่ leak secrets (host/user/password/tenant) | ✅ ผ่าน (ใหม่) |

## Verification

**ยืนยันแล้ว (automated, offline — ไม่ต้องใช้ live DB):**
1. ✅ `pytest backend/tests -q` → **207 passed** (174 เดิม + 33 ใหม่ Phase F) — คำสั่ง: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m pytest backend/tests -q`
2. ✅ `python -m compileall frontend scripts backend/app` ผ่าน (frontend/scripts ไม่มี syntax error)
3. ✅ (จากรอบก่อน, live) parity check คอลัมน์+row count ทั้ง 17 ตาราง — 16 OK, 1 รอ D-1
4. ✅ (จากรอบก่อน, live) query จริงด้วยชื่อคอลัมน์จริงผ่าน Postgres connector สำเร็จ

**ยังไม่ยืนยัน (manual gates — ห้าม claim ว่าเสร็จจนกว่าจะรันจริง):**

5. ⏳ **ทีมข้อมูล/DBA**: ปิด D-1 (แก้ชื่อคอลัมน์ CE1SATG) + D-2 (ส่ง numeric-cast mapping ครบ 17 ตาราง + ยืนยัน freshness/รอบ sync)
6. ⏳ **Parity re-run (live, read-only)** — หลัง D-1/D-2:
   ```powershell
   $env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\verify_pg_parity.py --json data\local\exports\pg_parity.json
   ```
   ต้องได้ `RESULT: parity OK` (exit 0) — ถ้า drift ให้ส่งรายงาน JSON กลับทีมข้อมูล
7. ⏳ **วาง D-2 mapping**: copy mapping เต็มไปที่ `data/local/knowledge/pg_numeric_columns.json` (รูปแบบตาม `data/templates/pg_numeric_columns.template.json`)
8. ⏳ **Live fallback smoke (read-only)** — Fabric เปิดปกติ: เช็ค `GET /api/v1/fabric/sources` ว่า `active_source="fabric"` → ตั้ง `FABRIC_SQL_ENABLED=false` ชั่วคราว + restart backend → เช็คอีกครั้งว่า `active_source="postgres"` และ sidebar แสดงสถานะสำรองสีเหลือง → คืนค่าเดิม
9. ⏳ **Live E2E ผ่าน LLM จริง** (รอ Ollama มี memory ว่าง): ตอน `FABRIC_SQL_ENABLED=false` ยิงคำถามยอดขายจริงผ่าน `POST /api/v1/chat/` → ตรวจว่า (ก) SQL ที่ generate เป็น PostgreSQL dialect + ใช้ `CAST(... AS DECIMAL(18,2))` กับคอลัมน์ varchar (ข) รันผ่าน Postgres สำเร็จ (ค) คำตอบสุดท้ายติดป้าย "แหล่งข้อมูล: Postgres mirror (สำรอง…)"
10. ⏳ **Human gate (owner)**: ยอมรับ freshness policy ของ mirror (จากคำตอบ D-2 ข้อ 3) ก่อนถือว่า fallback เปิดใช้จริงใน production

---

## ความเสี่ยง / ข้อควรระวัง
- **Type coercion asymmetry:** T-SQL อนุโลม implicit convert มากกว่า Postgres เสมอ — SQL ที่ผ่าน Fabric ไม่ได้แปลว่าจะผ่าน Postgres โดยอัตโนมัติ แม้ dialect syntax (TOP/LIMIT) จะแก้แล้วก็ตาม
- **Schema drift:** ถ้ามีคน alter table ฝั่งใดฝั่งหนึ่งในอนาคตโดยไม่ sync อีกฝั่ง จะไม่มีระบบเตือนอัตโนมัติแบบ real-time — มี `scripts/verify_pg_parity.py` ให้รันเป็นระยะ (แนะนำก่อน/หลังทุกรอบ migrate ฝั่งใดฝั่งหนึ่ง)
- **Freshness ที่ยังไม่ยืนยัน:** ถ้า Postgres mirror sync ไม่บ่อยพอ คำตอบตอน fallback อาจมาจากข้อมูลเก่ากว่าที่ CEO คาดหวัง — ต้องรอคำตอบจากทีมข้อมูล (D-2 ข้อ 3) — ระหว่างนี้ UI/รายงานติดป้ายเตือน "sync ล่าสุดอาจช้ากว่า Fabric" ทุกครั้งที่ใช้ fallback แล้ว (provenance label) เพื่อไม่ให้เข้าใจผิดว่าเป็นข้อมูลสด
