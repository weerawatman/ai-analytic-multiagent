# Phase F — Postgres WH_Silver Mirror (Auto-Fallback Data Source)

> **สถานะ:** โค้ด auto-fallback (dispatch + dialect-aware DA) implement และ push แล้ว (`b6eb496`) — แต่พบประเด็นจริงระหว่าง live verification 2 จุด (ดูหัวข้อ "Deep Audit") ที่ต้องให้ **ทีมข้อมูล/DBA** ตรวจ/แก้ก่อน ถึงจะยืนยันว่าใช้งานจริงได้ปลอดภัย — เอกสารนี้คือ handoff ให้ทีมข้อมูลทำงานส่วนของเขาก่อน แล้วนำกลับมาให้ dev ทำงานฝั่งโค้ดต่อ (ดูหัวข้อ "งานฝั่งโค้ดที่เหลือ")
> **ผู้ดำเนินการ:** ทีมข้อมูล/DBA ทำ D-1/D-2 ก่อน (checklist ด้านล่าง) → ส่งผลกลับ owner → owner ส่งต่อ dev ทำ "งานฝั่งโค้ดที่เหลือ"
> **หลักการใหญ่:** Fabric capacity ไม่เสถียร — Postgres ที่ mirror ข้อมูลเดียวกัน (`fabric_WH_Silver` บน `172.16.0.70`) ใช้เป็น **auto-fallback** เมื่อ Fabric unreachable/paused เท่านั้น ไม่ใช่ตัวแทนถาวร — Fabric ยังเป็น source หลักเสมอ

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

## งานฝั่งโค้ดที่เหลือ (dev ทำต่อหลัง D-1/D-2 เสร็จ)

1. เพิ่มคำแนะนำ CAST แบบ dialect-portable (`CAST(col AS DECIMAL(18,2))` ใช้ได้ทั้ง T-SQL และ PostgreSQL) ใน `data_analyst/SKILL.md` และ/หรือ `SYSTEM_PROMPT` (`backend/app/agents/data_analyst.py`) สำหรับคอลัมน์ที่ schema บอกว่าเป็น varchar แต่ใช้ aggregate/compare เชิงตัวเลข
2. ถ้าทีมข้อมูลเลือกทาง (ข): เสริม schema context pack ให้ DA เห็นว่าคอลัมน์ไหนเป็น numeric จริงบน Postgres ตอน `source="postgres"` (ปัจจุบัน DA ใช้ discovery.json ของ Fabric ล้วนๆ ไม่ว่าจะรันจริงกับ source ไหน)
3. เก็บ parity-check script ที่ใช้ตรวจรอบนี้ไว้เป็น `scripts/verify-pg-parity.py` ถ้า owner ต้องการรันซ้ำเป็นระยะ (กัน schema drift ระหว่าง Fabric/Postgres ในอนาคต)
4. Live end-to-end ผ่าน LLM จริง — บล็อกอยู่ตอนนี้เพราะเครื่อง dev out-of-memory ตอนโหลด Ollama model (ไม่เกี่ยวกับโค้ด) รอ resource ว่างแล้วยิงคำถามจริงผ่าน `/api/v1/chat/` ตอน `FABRIC_SQL_ENABLED=false` ดูว่า LLM cast ถูกต้องจริงในทางปฏิบัติ

---

## Tests (เพิ่มแล้วในรอบ implement — ครอบคลุม mechanism แต่ไม่ครอบคลุม data-parity เพราะต้องใช้ live DB)

| ไฟล์ | ครอบคลุม |
|---|---|
| `test_postgres_replica.py` | connector: is_configured, connect (readonly+statement_timeout), execute_read_only, fetch_schema_summary (LIMIT ไม่ใช่ TOP, กรอง system catalog) |
| `test_sql_source_dispatch.py` | `get_active_sql_source`, reachability TTL cache, `run_sql` dispatch, row-count guard source-aware |
| `test_data_analyst_postgres_fallback.py` | DA เขียน SQL ตรง dialect ตาม source, retry สลับ dialect กลางคัน, `_classify_sql_error` รู้จัก psycopg2/Postgres SQLSTATE |
| ⏳ ยังไม่มี | test สำหรับ CAST guidance (รอ D-2 ตัดสินใจก่อนถึงจะเขียนได้ตรงจุด) |

## Verification
1. ✅ **ทำแล้ว**: parity check คอลัมน์+row count ทั้ง 17 ตาราง (live) — 16 OK, 1 มีสาเหตุชัดเจนรอ D-1
2. ✅ **ทำแล้ว**: query จริงด้วยชื่อคอลัมน์จริงผ่าน Postgres connector สำเร็จ
3. ⏳ รอทีมข้อมูลตอบ D-2 → เพิ่ม CAST guidance → `pytest backend/tests -q` ต้องผ่านหมด (174+ tests) + test ใหม่เฉพาะ CAST
4. ⏳ รอ Ollama มี memory ว่าง → live E2E ผ่าน LLM จริงตอน Fabric ปิด → ตรวจ SQL ที่ generate จริงว่า cast ถูกและรันผ่าน Postgres

---

## ความเสี่ยง / ข้อควรระวัง
- **Type coercion asymmetry:** T-SQL อนุโลม implicit convert มากกว่า Postgres เสมอ — SQL ที่ผ่าน Fabric ไม่ได้แปลว่าจะผ่าน Postgres โดยอัตโนมัติ แม้ dialect syntax (TOP/LIMIT) จะแก้แล้วก็ตาม
- **Schema drift:** ถ้ามีคน alter table ฝั่งใดฝั่งหนึ่งในอนาคตโดยไม่ sync อีกฝั่ง จะไม่มีระบบเตือนอัตโนมัติ (แนะนำเก็บ parity script ไว้รันเป็นระยะตามข้อ 3 ใน "งานฝั่งโค้ดที่เหลือ")
- **Freshness ที่ยังไม่ยืนยัน:** ถ้า Postgres mirror sync ไม่บ่อยพอ คำตอบตอน fallback อาจมาจากข้อมูลเก่ากว่าที่ CEO คาดหวัง — ต้องรอคำตอบจากทีมข้อมูล (D-2 ข้อ 3)
