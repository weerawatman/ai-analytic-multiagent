# WH_Silver T-SQL Reference — คู่มือจัดเก็บไฟล์อ้างอิง

โฟลเดอร์นี้เป็น **เทมเพลตที่ commit ใน Git** สำหรับอ้างอิงรูปแบบไฟล์ T-SQL จาก WH_Silver  
ไฟล์จริงที่ใช้งาน runtime อยู่ที่ `data/local/knowledge/sql_reference/` (gitignored)

โครงสร้างสะท้อน repo จริง `SAT_Fabric_Knowledge/01_SQL/WH_Silver/SAPHANADB/` — sync ด้วยสคริปต์แทนการ copy มือ

---

## โครงสร้างโฟลเดอร์

```
data/templates/sql_reference/          ← เทมเพลต (committed)
├── README.md
├── _manifest.template.json            ← schema index ไฟล์ SQL
└── SAPHANADB/
    ├── Tables/                        ← DDL / cleaned table definitions
    └── StoredProcedures/              ← usp_Load_* load logic

data/local/knowledge/sql_reference/      ← ไฟล์จริง (runtime, gitignored)
├── _manifest.json
└── SAPHANADB/
    ├── Tables/
    └── StoredProcedures/
```

---

## ไฟล์ที่คาดหวัง (จาก WH_Silver repo)

### `SAPHANADB/Tables/` — table DDL / cleaned definitions

| ไฟล์ | หมายเหตุ |
|------|----------|
| `ACDOCA_All_Cleaned.sql` | Universal Journal |
| `CE1SAIG_All_Cleaned.sql` | CO-PA line items |
| `COSP_All_Cleaned.sql` | CO object totals (period) |
| `COSS_All_Cleaned.sql` | CO object totals (year) |
| `VBRK_All_Cleaned.sql` | Billing header |
| `VBRP_All_Cleaned.sql` | Billing items |
| `Dim_CSKT_Cleaned.sql` | Cost center text (dim) |
| `Dim_KNA1_Cleaned.sql` | Customer master (dim) |
| `Dim_MAKT_Cleaned.sql` | Material description (dim) |
| `Dim_MARA_Cleaned.sql` | Material master (dim) |
| `Dim_SG-A_Dept.sql` | SG-A department dim |
| `Dim_SKAT_Cleaned.sql` | G/L account text (dim) |
| `Dim_T001_Cleaned.sql` | Company code (dim) |
| `Dim_TVKOT_Cleaned.sql` | Sales org text (dim) |
| `CSKT_Cleaned.sql` | Cost center text |
| `SKAT_Cleaned.sql` | G/L account text |

### `SAPHANADB/StoredProcedures/` — load procedures

| ไฟล์ | หมายเหตุ |
|------|----------|
| `usp_Load_ACDOCA_Month.sql` | โหลด ACDOCA รายเดือน |
| `usp_Load_CE1SATG_Month.sql` | โหลด CE1 รายเดือน |
| `usp_Load_COSP_Year.sql` | โหลด COSP รายปี |
| `usp_Load_COSS_Year.sql` | โหลด COSS รายปี |
| `usp_Load_VBRK_Month.sql` | โหลด VBRK รายเดือน |
| `usp_Load_VBRP_Month.sql` | โหลด VBRP รายเดือน |

---

## Sync จาก repo WH_Silver (แนะนำ)

1. ตั้ง path โฟลเดอร์ต้นทาง (root ที่มี `SAPHANADB/` อยู่ข้างใน) เช่น  
   `C:\SAT_Fabric_Knowledge\01_SQL\WH_Silver`

2. รันสคริปต์ sync (copy + สร้าง `_manifest.json` อัตโนมัติ):

   ```powershell
   .\scripts\sync-wh-silver-sql.ps1 -SourcePath "C:\SAT_Fabric_Knowledge\01_SQL\WH_Silver"
   ```

3. ตรวจสอบผลที่ `data/local/knowledge/sql_reference/`

4. **รีสตาร์ท backend** หากต้องการให้ระบบเห็น manifest ใหม่ (loader integration อยู่ใน sprint ถัดไป)

---

## วิธีเพิ่ม / อัปเดตด้วยมือ

1. **คัดลอกไฟล์ SQL** ไปยัง `data/local/knowledge/sql_reference/SAPHANADB/Tables/` หรือ `.../StoredProcedures/`
2. **อัปเดต** `data/local/knowledge/sql_reference/_manifest.json` — เพิ่มรายการใน `items[]`:

   | ฟิลด์ | คำอธิบาย |
   |-------|----------|
   | `id` | รหัสสั้น unique (snake_case) |
   | `schema` | schema ใน Fabric เช่น `SAPHANADB` |
   | `table_ref` | ชื่อเต็ม เช่น `SAPHANADB.VBRK_All_Cleaned` หรือ `SAPHANADB.usp_Load_VBRK_Month` |
   | `file_path` | path สัมพัทธ์จาก `sql_reference/` เช่น `SAPHANADB/Tables/VBRK_All_Cleaned.sql` |
   | `kind` | `table_ddl` (Tables) หรือ `load_sp` (StoredProcedures) |
   | `description_th` | คำอธิบายสั้นเป็นภาษาไทย |
   | `themes` | รายการ theme_id ที่เกี่ยวข้อง (optional) |
   | `tags` | แท็กค้นหา (optional) |

---

## ประเภทไฟล์ SQL ที่รองรับ

| `kind` | โฟลเดอร์ | เนื้อหาที่คาดหวัง |
|--------|----------|-------------------|
| `table_ddl` | `Tables/` | `CREATE TABLE` / view DDL / cleaned table definition — **ใช้ map คอลัมน์และ rename** |
| `load_sp` | `StoredProcedures/` | `CREATE PROCEDURE usp_Load_*` — **ใช้เข้าใจ load logic และ filter ช่วงเวลา** |

---

## การ map กับ repo ต้นทาง

| Repo ต้นทาง (`WH_Silver/`) | ในโปรเจกต์นี้ |
|----------------------------|----------------|
| `SAPHANADB/Tables/*.sql` | `data/local/knowledge/sql_reference/SAPHANADB/Tables/` |
| `SAPHANADB/StoredProcedures/*.sql` | `data/local/knowledge/sql_reference/SAPHANADB/StoredProcedures/` |
| (ไม่ sync) `WH_Silver.sqlproj`, `xmla.json`, `SAPHANADB.sql` | ไม่จำเป็นสำหรับ agent reference |

---

## หมายเหตุ

- ไฟล์ใน `data/local/` **ไม่ถูก commit** — backup เองหรือ sync ซ้ำจาก repo ต้นทาง
- อ่านอย่างเดียวจาก Fabric — อย่า execute write DDL ผ่านระบบนี้
- เทมเพลตในโฟลเดอร์นี้ใช้เป็น reference เมื่อ onboard สมาชิกใหม่
